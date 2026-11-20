#!/usr/bin/env python3
"""
audit_antigravity_sqlite.py — Zero-dependency read-only forensic auditor for Google Antigravity local SQLite DBs.

Scans local conversation databases (`conversations/*.db`) in read-only mode (`?immutable=1`),
decodes Google's `gen_metadata` protobuf billing records, and prints:
  1. UI Model Label (`field 21`) vs. Actual Backend Model ID (`field 19`) routing table
  2. Daily `thinking_tokens == 0` rates and median/mean reasoning tokens by model
  3. Strict same-model follow-up KV Cache (`cached_input_tokens == 0`) failure rates & overbilled tokens

Privacy & Safety:
  - 100% local & read-only. Makes zero network requests.
  - Never reads prompt text, file contents, OAuth tokens, or user identifiers.
"""

import collections
import datetime
import json
import os
import pathlib
import platform
import sqlite3
import statistics
import sys


def default_base_dirs():
    home = pathlib.Path.home()
    candidates = [
        home / ".gemini" / "antigravity",
        home / ".gemini" / "antigravity-cli",
        home / ".gemini" / "antigravity-ide",
        home / ".gemini" / "antigravity-backup",
    ]
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        localappdata = os.environ.get("LOCALAPPDATA")
        for root in (appdata, localappdata):
            if root:
                candidates.append(pathlib.Path(root) / "Antigravity")
                candidates.append(pathlib.Path(root) / "antigravity")
    return [p for p in candidates if p.exists()]


def decode_proto(buf, depth=0):
    i, n = 0, len(buf)
    out = []
    while i < n:
        tag, shift = 0, 0
        while i < n:
            b = buf[i]
            i += 1
            tag |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        fn, wt = tag >> 3, tag & 7
        if fn == 0:
            break
        if wt == 0:  # varint
            val, shift = 0, 0
            while i < n:
                b = buf[i]
                i += 1
                val |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            out.append((fn, "v", val))
        elif wt == 2:  # length-delimited
            ln, shift = 0, 0
            while i < n:
                b = buf[i]
                i += 1
                ln |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            if i + ln > n:
                break
            sub = buf[i : i + ln]
            i += ln
            try:
                s = sub.decode("utf-8")
                if all(32 <= ord(c) < 127 or c in "\n\r\t" for c in s):
                    out.append((fn, "s", s))
                    continue
            except Exception:
                pass
            if depth < 3 and ln > 0:
                try:
                    nested = decode_proto(sub, depth + 1)
                    if nested:
                        out.append((fn, "m", nested))
                        continue
                except Exception:
                    pass
            out.append((fn, "b", sub))
        elif wt == 1:
            i += 8
        elif wt == 5:
            i += 4
        else:
            break
    return out


def main():
    extra_dirs = [pathlib.Path(a) for a in sys.argv[1:]]
    roots = default_base_dirs() + [p for p in extra_dirs if p.exists()]
    if not roots:
        print("No Antigravity directories found. Pass custom directory paths as arguments.")
        sys.exit(1)

    best_dbs = {}
    best_transcripts = {}
    for root in roots:
        conv_dir = root / "conversations" if (root / "conversations").exists() else root
        for db in conv_dir.glob("*.db"):
            try:
                rp = db.resolve()
                if not rp.exists():
                    continue
                cid = db.stem
                sz, mt = rp.stat().st_size, rp.stat().st_mtime
                if cid not in best_dbs or (sz, mt) > (best_dbs[cid][1], best_dbs[cid][2]):
                    best_dbs[cid] = (rp, sz, mt)
            except Exception:
                pass

        brain_dir = root / "brain"
        if brain_dir.exists():
            for sub in brain_dir.iterdir():
                if not sub.is_dir():
                    continue
                for fn in ("transcript.jsonl", "transcript_full.jsonl"):
                    tp = sub / ".system_generated" / "logs" / fn
                    if tp.exists():
                        try:
                            rp = tp.resolve()
                            sz = rp.stat().st_size
                            if sub.name not in best_transcripts or sz > best_transcripts[sub.name][1]:
                                best_transcripts[sub.name] = (rp, sz)
                        except Exception:
                            pass
                        break

    routing = collections.Counter()
    calls = []

    for cid, (db_path, _, mt) in sorted(best_dbs.items()):
        step_ts = {}
        first_dt = None
        if cid in best_transcripts:
            try:
                with open(best_transcripts[cid][0], "r", errors="replace") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        obj = json.loads(line)
                        ts = obj.get("created_at")
                        si = obj.get("step_index")
                        if ts:
                            dt = datetime.datetime.fromisoformat(ts.rstrip("Z").split(".")[0])
                            if si is not None:
                                step_ts[int(si)] = dt
                            if first_dt is None:
                                first_dt = dt
            except Exception:
                pass

        fallback_dt = first_dt or datetime.datetime.fromtimestamp(mt, datetime.timezone.utc).replace(tzinfo=None)
        try:
            con = sqlite3.connect(f"file:{db_path}?immutable=1", uri=True)
            rows = con.execute("SELECT idx, data FROM gen_metadata ORDER BY idx").fetchall()
            con.close()
        except Exception:
            continue

        prev_by_traj = {}
        for idx, data in rows:
            try:
                top = decode_proto(data)
            except Exception:
                continue
            cm_list = [v for k, t, v in top if k == 1 and t == "m"]
            if not cm_list:
                continue
            cm = cm_list[0]
            u_list = [v for k, t, v in cm if k == 4 and t == "m"]
            usage = u_list[0] if u_list else []
            u_map = {k: v for k, t, v in usage if t in ("v", "s")}

            be_model = next((v for k, t, v in cm if k == 19 and t == "s"), "unknown")
            ui_model = next((v for k, t, v in cm if k == 21 and t == "s"), "unknown")
            kv20 = {}
            for k, t, v in cm:
                if k == 20 and t == "m":
                    sk = next((vv for kk, tt, vv in v if kk == 1 and tt == "s"), None)
                    sv = next((vv for kk, tt, vv in v if kk == 2 and tt == "s"), None)
                    if sk:
                        kv20[sk] = sv

            last_step = int(kv20["last_step_index"]) if kv20.get("last_step_index", "").isdigit() else -1
            traj_id = kv20.get("trajectory_id", cid)
            dt = next((step_ts[s] for s in (last_step + 1, last_step, last_step + 2) if s in step_ts), fallback_dt)

            uncached_in = u_map.get(2, 0)
            cached_in = u_map.get(5, 0)
            total_in = uncached_in + cached_in
            thinking_tok = u_map.get(9, 0)
            enum_id = u_map.get(1, 0)

            routing[(ui_model, be_model, enum_id)] += 1
            prev = prev_by_traj.get(traj_id)
            gap = (dt - prev["dt"]).total_seconds() if prev else None

            rec = {
                "date": dt.strftime("%Y-%m-%d"),
                "dt": dt,
                "ui": ui_model,
                "be": be_model,
                "uncached_in": uncached_in,
                "cached_in": cached_in,
                "total_in": total_in,
                "thinking_tok": thinking_tok,
                "same_be_prev": bool(prev and prev["be"] == be_model and be_model != "unknown"),
                "gap": gap,
                "prev_in": prev["total_in"] if prev else 0,
            }
            calls.append(rec)
            prev_by_traj[traj_id] = rec

    print(f"Scanned {len(best_dbs)} unique conversation DBs | Decoded {len(calls):,} LLM billing records\n")

    print("=== 1. UI MODEL LABEL (field 21) vs. ACTUAL BACKEND MODEL (field 19) ===")
    for (ui, be, enum_id), cnt in routing.most_common():
        flag = "  <-- MISMATCH / TIERED" if ("tiered" in be or "flash-worker" in be or "trial" in be) else ""
        print(f"  {cnt:6d}x | UI: {ui:34s} | Backend: {be:30s} | enum={enum_id}{flag}")

    print("\n=== 2. THINKING TOKENS BY MODEL & DATE (Excluding 3P Claude & Aborted Calls) ===")
    by_think = collections.defaultdict(list)
    for c in calls:
        if c["be"] == "unknown" or "claude" in c["be"].lower():
            continue
        by_think[(c["ui"], c["be"], c["date"])].append(c["thinking_tok"])
    for (ui, be, d), vals in sorted(by_think.items()):
        z = sum(1 for v in vals if v == 0)
        print(
            f"  {d} | {ui:32s} ({be:28s}) | n={len(vals):4d} | "
            f"think=0: {z:4d} ({z*100/len(vals):5.1f}%) | med={int(statistics.median(vals)):4d} | avg={int(statistics.mean(vals)):4d}"
        )

    print("\n=== 3. STRICT KV CACHE AUDIT (Same Backend Model, No Compaction, Gap <= 45s, Input >= 15k) ===")
    by_cache = collections.defaultdict(list)
    for c in calls:
        if c["same_be_prev"] and c["gap"] is not None and 0 <= c["gap"] <= 45:
            if c["total_in"] >= 15000 and c["total_in"] >= c["prev_in"] * 0.98:
                by_cache[(c["ui"], c["date"])].append(c)

    total_gemini_overbilled = 0
    for (ui, d), items in sorted(by_cache.items()):
        z = [x for x in items if x["cached_in"] == 0]
        wasted = sum(x["uncached_in"] for x in z)
        if "Claude" not in ui:
            total_gemini_overbilled += wasted
        tot_in = sum(x["total_in"] for x in items)
        tot_ca = sum(x["cached_in"] for x in items)
        print(
            f"  {d} | {ui:32s} | turns={len(items):4d} | "
            f"0%_cache={len(z):3d} ({len(z)*100/len(items):5.1f}%) | hit_rate={tot_ca*100/tot_in:5.1f}% | overbilled_uncached={wasted:,}"
        )
    print(f"\nTotal strict (<45s, non-compacted) overbilled Gemini uncached input tokens: {total_gemini_overbilled:,}")


if __name__ == "__main__":
    main()
