#!/usr/bin/env python3
"""
audit_antigravity_sqlite.py (v1.1) — Zero-dependency, read-only forensic auditor
for Google Antigravity local SQLite conversation databases.

Scans local conversation databases (`conversations/*.db`) in read-only mode
(`?immutable=1`), decodes Google's `gen_metadata` protobuf billing records, and prints:
  0. Algebraic protobuf schema closure check (`usage.3 == usage.9 + usage.10`)
     and strict `ResponseID` (`usage.11`) deduplication stats across forked/Swarm DBs
  1. UI Model Label (`field 21`) vs. Actual Backend Model ID (`field 19`) routing table
  2. Thinking tokens by model & date (`think=0` %, median p50, mean, p90, p95)
  3. Strict KV Cache Audit (`<= 45s` & `<= 300s`, same backend model, no compaction,
     real per-step transcript timestamps required on BOTH turns — never file mtime)
  4. Measured server latency / TTFT wait-time penalty (`>=100K` warm vs. 0%-cache cold)

Privacy & Safety:
  - 100% local & read-only. Makes zero network requests.
  - Never reads prompt text, file contents, OAuth tokens, or user identifiers.

Usage:
  python3 audit_antigravity_sqlite.py [extra_dirs...] [--since YYYY-MM-DD] [--until YYYY-MM-DD]
"""

import argparse
import collections
import datetime
import json
import os
import pathlib
import platform
import sqlite3
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
        for env_key in ("APPDATA", "LOCALAPPDATA"):
            root = os.environ.get(env_key)
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


def parse_proto_duration(msg_list):
    if not msg_list:
        return 0.0
    sec = nanos = 0
    for k, t, v in msg_list[0]:
        if k == 1 and t == "v":
            sec = v
        elif k == 2 and t == "v":
            nanos = v
    return sec + nanos / 1e9


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * p))
    return sorted_vals[idx]


def print_cache_window(calls, max_gap_sec, label):
    print(
        f"\n=== {label} (Same Backend Model, No Compaction >=98% prev_in, "
        f"Real Step Timestamps, Gap <= {max_gap_sec}s, Input >= 15k) ==="
    )
    by_cache = collections.defaultdict(list)
    for c in calls:
        if (
            c["same_be_prev"]
            and c["both_real_ts"]
            and c["gap"] is not None
            and 0 <= c["gap"] <= max_gap_sec
            and c["total_in"] >= 15000
            and c["total_in"] >= c["prev_in"] * 0.98
        ):
            by_cache[(c["ui"], c["date"])].append(c)

    gem_turns = gem_zero = gem_wasted = 0
    cl_turns = cl_zero = cl_wasted = 0
    for (ui, d), items in sorted(by_cache.items()):
        z = [x for x in items if x["cached_in"] == 0]
        wasted = sum(x["uncached_in"] for x in z)
        is_claude = "Claude" in ui or any("claude" in x["be"].lower() for x in items)
        if is_claude:
            cl_turns += len(items)
            cl_zero += len(z)
            cl_wasted += wasted
        else:
            gem_turns += len(items)
            gem_zero += len(z)
            gem_wasted += wasted
        tot_in = sum(x["total_in"] for x in items)
        tot_ca = sum(x["cached_in"] for x in items)
        print(
            f"  {d} | {ui:32s} | turns={len(items):4d} | "
            f"0%_cache={len(z):3d} ({len(z)*100/len(items):5.1f}%) | "
            f"hit_rate={tot_ca*100/tot_in:5.1f}% | overbilled_uncached={wasted:,}"
        )
    print(
        f"  --> GEMINI TOTAL (<={max_gap_sec}s): turns={gem_turns:,} | "
        f"0%_cache={gem_zero:,} ({gem_zero*100/max(1,gem_turns):.2f}%) | "
        f"overbilled_uncached={gem_wasted:,}"
    )
    print(
        f"  --> CLAUDE CONTROL (<={max_gap_sec}s): turns={cl_turns:,} | "
        f"0%_cache={cl_zero:,} ({cl_zero*100/max(1,cl_turns):.2f}%) | "
        f"overbilled_uncached={cl_wasted:,}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Read-only forensic auditor for Google Antigravity local SQLite DBs (v1.1)."
    )
    parser.add_argument("extra_dirs", nargs="*", help="Optional custom Antigravity directories")
    parser.add_argument("--since", default=None, help="Optional inclusive start UTC date (YYYY-MM-DD)")
    parser.add_argument("--until", default=None, help="Optional inclusive end UTC date (YYYY-MM-DD)")
    args = parser.parse_args()

    extra = [pathlib.Path(a) for a in args.extra_dirs if pathlib.Path(a).exists()]
    roots = default_base_dirs() + extra
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
    seen_resp_ids = set()
    raw_rows = dup_rows = missing_ts_rows = 0
    closure_exact = closure_mismatch = 0

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
            raw_rows += 1

            u_list = [v for k, t, v in cm if k == 4 and t == "m"]
            usage = u_list[0] if u_list else []
            u_map = {k: v for k, t, v in usage if t in ("v", "s")}

            be_model = next((v for k, t, v in cm if k == 19 and t == "s"), "unknown")
            ui_model = next((v for k, t, v in cm if k == 21 and t == "s"), "unknown")
            d11 = parse_proto_duration([v for k, t, v in cm if k == 11 and t == "m"])
            d12 = parse_proto_duration([v for k, t, v in cm if k == 12 and t == "m"])

            kv20 = {}
            for k, t, v in cm:
                if k == 20 and t == "m":
                    sk = next((vv for kk, tt, vv in v if kk == 1 and tt == "s"), None)
                    sv = next((vv for kk, tt, vv in v if kk == 2 and tt == "s"), None)
                    if sk:
                        kv20[sk] = sv

            last_step = int(kv20["last_step_index"]) if kv20.get("last_step_index", "").isdigit() else -1
            traj_id = kv20.get("trajectory_id", cid)
            resp_id = u_map.get(11, "")

            real_dt = next((step_ts[s] for s in (last_step + 1, last_step, last_step + 2) if s in step_ts), None)
            has_real_ts = real_dt is not None
            dt = real_dt or fallback_dt

            uncached_in = u_map.get(2, 0)
            total_out = u_map.get(3, 0)
            cached_in = u_map.get(5, 0)
            thinking_tok = u_map.get(9, 0)
            resp_out = u_map.get(10, 0)
            total_in = uncached_in + cached_in
            enum_id = u_map.get(1, 0)

            # Algebraic identity check across all non-zero rows
            if total_out > 0 and (thinking_tok > 0 or resp_out > 0):
                if total_out == thinking_tok + resp_out:
                    closure_exact += 1
                else:
                    closure_mismatch += 1

            # Strict ResponseID deduplication (prevents forked/Swarm DB double-counting)
            is_dup = False
            if resp_id:
                if resp_id in seen_resp_ids:
                    is_dup = True
                    dup_rows += 1
                else:
                    seen_resp_ids.add(resp_id)

            prev = prev_by_traj.get(traj_id)
            both_real_ts = bool(prev and has_real_ts and prev["has_real_ts"])
            gap = (dt - prev["dt"]).total_seconds() if (prev and both_real_ts) else None

            rec = {
                "date": dt.strftime("%Y-%m-%d"),
                "dt": dt,
                "has_real_ts": has_real_ts,
                "both_real_ts": both_real_ts,
                "ui": ui_model,
                "be": be_model,
                "enum_id": enum_id,
                "uncached_in": uncached_in,
                "cached_in": cached_in,
                "total_in": total_in,
                "thinking_tok": thinking_tok,
                "d11": d11,
                "d12": d12,
                "same_be_prev": bool(prev and prev["be"] == be_model and be_model != "unknown"),
                "gap": gap,
                "prev_in": prev["total_in"] if prev else 0,
            }
            prev_by_traj[traj_id] = rec

            if is_dup:
                continue
            if not has_real_ts:
                missing_ts_rows += 1
            if args.since and rec["date"] < args.since:
                continue
            if args.until and rec["date"] > args.until:
                continue

            routing[(ui_model, be_model, enum_id)] += 1
            calls.append(rec)

    date_note = ""
    if args.since or args.until:
        date_note = f" | Date Filter: {args.since or '*'} .. {args.until or '*'}"
    print(
        f"Audit v1.1 | Scanned {len(best_dbs)} unique DBs | Raw rows={raw_rows:,} | "
        f"Fork/Swarm ResponseID duplicates skipped={dup_rows:,} | Unique records analyzed={len(calls):,}{date_note}"
    )
    print(
        f"Schema self-check (usage.3 == usage.9 + usage.10): "
        f"{closure_exact:,} exact / {closure_mismatch} mismatches | "
        f"Rows lacking per-step transcript ts (excluded from gap audit): {missing_ts_rows:,}\n"
    )

    print("=== 1. UI MODEL LABEL (field 21) vs. ACTUAL BACKEND MODEL (field 19) [Deduplicated] ===")
    for (ui, be, enum_id), cnt in routing.most_common():
        flag = "  <-- MISMATCH / TIERED" if ("tiered" in be or "flash-worker" in be or "trial" in be) else ""
        print(f"  {cnt:6d}x | UI: {ui:34s} | Backend: {be:30s} | enum={enum_id}{flag}")

    print("\n=== 2. THINKING TOKENS BY MODEL & DATE (Excluding 3P Claude & Aborted Calls) ===")
    by_think = collections.defaultdict(list)
    by_be_pooled = collections.defaultdict(list)
    for c in calls:
        if c["be"] == "unknown" or "claude" in c["be"].lower():
            continue
        by_think[(c["ui"], c["be"], c["date"])].append(c["thinking_tok"])
        by_be_pooled[(c["ui"], c["be"])].append(c["thinking_tok"])
    for (ui, be, d), vals in sorted(by_think.items()):
        s = sorted(vals)
        z = sum(1 for v in s if v == 0)
        print(
            f"  {d} | {ui:32s} ({be:28s}) | n={len(s):4d} | "
            f"think=0: {z:4d} ({z*100/len(s):5.1f}%) | "
            f"p50={percentile(s, 0.50):4d} mean={int(sum(s)/len(s)):4d} "
            f"p90={percentile(s, 0.90):4d} p95={percentile(s, 0.95):5d}"
        )

    print("\n--- Pooled Thinking Percentiles for UI 'Gemini 4 Hydrogen (High)' ---")
    for (ui, be), vals in sorted(by_be_pooled.items()):
        if ui == "Gemini 4 Hydrogen (High)":
            s = sorted(vals)
            print(
                f"  {be:30s} | n={len(s):4d} | mean={sum(s)/len(s):6.1f} | "
                f"p50={percentile(s,0.50):4d} | p75={percentile(s,0.75):4d} | "
                f"p90={percentile(s,0.90):4d} | p95={percentile(s,0.95):5d}"
            )

    print_cache_window(calls, 45, "3A. STRICT KV CACHE AUDIT (<=45s)")
    print_cache_window(calls, 300, "3B. 5-MINUTE WINDOW KV CACHE AUDIT (<=300s)")

    warm_d11, cold_d11 = [], []
    cold_ttft_sum = cold_tot_sum = 0.0
    cold_cnt = 0
    for c in calls:
        if "claude" in c["be"].lower() or c["be"] == "unknown":
            continue
        if (
            c["same_be_prev"]
            and c["both_real_ts"]
            and c["gap"] is not None
            and 0 <= c["gap"] <= 300
            and c["total_in"] >= 15000
            and c["total_in"] >= c["prev_in"] * 0.98
        ):
            if c["cached_in"] == 0:
                cold_cnt += 1
                cold_ttft_sum += c["d11"]
                cold_tot_sum += c["d11"] + c["d12"]
                if c["total_in"] >= 100000:
                    cold_d11.append(c["d11"])
            elif c["total_in"] >= 100000:
                warm_d11.append(c["d11"])
    warm_d11.sort()
    cold_d11.sort()
    print("\n=== 4. MEASURED SERVER WAIT / LATENCY PENALTY (<=300s Gemini Follow-ups) ===")
    if warm_d11 and cold_d11:
        w_med = percentile(warm_d11, 0.50)
        c_med = percentile(cold_d11, 0.50)
        print(
            f"  >=100K context median TTFT (d11): warm={w_med:.2f}s (n={len(warm_d11):,}) vs "
            f"0%-cache cold={c_med:.2f}s (n={len(cold_d11):,}) -> {c_med/max(0.01,w_med):.2f}x slower"
        )
    print(
        f"  Across {cold_cnt:,} 0%-cache wipes (<=300s): "
        f"TTFT wait={cold_ttft_sum/60:.1f} min | Total turn wait={cold_tot_sum/60:.1f} min"
    )


if __name__ == "__main__":
    main()
