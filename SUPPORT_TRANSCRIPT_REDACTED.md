# Verbatim Google One Support Chat Transcript (PII-Redacted)

* **Date:** November 20, 2026 (`15:54 – 16:37`)
* **Plan:** Google One AI Ultra (20x tier, `$199.99/month`, 30 TB Storage)
* **Redactions Applied:** Subscriber initials (`[Subscriber]`), first name (`[REDACTED_NAME]`), email address (`[REDACTED_EMAIL]`), Support Case ID (`[REDACTED_CASE_ID]`), and the trailing characters of server-side `ResponseID`s (`****`) to prevent account correlation while preserving full technical context.

---

**[15:54] [Agent] • Support Specialist:**
Welcome! Your Case ID is `[REDACTED_CASE_ID]`. Refer to this if you need to contact us again. By the way, the chat will stay open for 24 hours after your last message. If you step away for any reason, you can come back to this chat.

**[15:54] [Agent] • Support Specialist:**
Hi ! Thanks for getting in touch with Google one. My name is [Agent].

**[15:54] [Subscriber]:**
Hi, I am a paying Google One AI Ultra (20x tier, $199.99/month) subscriber requesting a billing refund/credit for this billing cycle due to severe "Service Not As Described" and server-side quota overbilling between Nov 15 and Nov 20, 2026, and please provide my official Case ID in this chat. This is a billing dispute regarding paid Ultra 20x capacity I paid $199.99/mo for—not a technical support question. Over 23,515 logged requests in Google Antigravity, Google's backend suffered documented regressions that falsely drained my paid 5-hour/7-day Ultra quota and silently downgraded model delivery. I am pasting the exact server-side Google ResponseIDs in my next message.

**[15:55] [Subscriber]:**
Verified server telemetry from my account (Nov 15-20, 2026):
1. 0% KV Cache Bug Overbilling Quota: Gemini 4 repeatedly dropped cached_input_tokens to 0 on consecutive turns <25s apart, overbilling ~49.5M uncached tokens against my paid Ultra quota (while hosted Claude in the exact same app had 0 failures across 623 turns). Proof ResponseIDs: `RsD_aortBZmo****` -> `k8P_avL6B9bN****` (470,280 uncached, 0 cached) -> `q8P_arKjJ6-F****` (474,739 uncached, 0 cached); also `y3T-auazErDc****` & `ZHX-auGSEqqf****` (3.26M uncached in 150s).
2. Reasoning & Routing Degradation: Gemini 4 Argon zero-thinking rate spiked from 0.3% to 64.9% (e.g. ResponseID `PfP8aoOXNPuG****`), and Hydrogen High silently switched to `"gemini-4-hydrogen-tiered-high"` with >60% less reasoning.
3. Failed empty responses still burned quota until hitting 429 RESOURCE_EXHAUSTED.
Please issue a 1-month billing refund/credit on my Ultra 20x plan, or escalate me to a Tier-2 Billing Supervisor.

**[15:55] [Agent] • Support Specialist:**
Thanks for giving me all the details about your concern. No worries, I'll be more than glad to check this out for you and exhaust everything I've got to check this out.

**[15:56] [Agent] • Support Specialist:**
Before we proceed kindly confirm if were currently working on with this email address `[REDACTED_EMAIL]`?

**[15:56] [Subscriber]:**
yes

**[15:57] [Subscriber]:**
Thank you, I really appreciate your help looking into this. Please take your time, and whenever convenient, could you also share the Case ID for this chat so I have it for my records?

**[15:58] [Agent] • Support Specialist:**
You're welcome and thanks for confirming

**[15:59] [Agent] • Support Specialist:**
Here is the case ID `[REDACTED_CASE_ID]`

**[15:59] [Agent] • Support Specialist:**
Just to confirm, may I know your name please?

**[15:59] [Subscriber]:**
`[REDACTED_NAME]`

**[15:59] [Agent] • Support Specialist:**
Thanks for confirming

**[16:00] [Agent] • Support Specialist:**
Google storage plan purchases are non-refundable. The amount of storage you purchased is yours for the length of the subscription, even if you decide to cancel it. But I will be more than happy to try and request for a one time courtesy refund for you.

**[16:00] [Agent] • Support Specialist:**
Let me set your proper expectation that Google is just a payment processor and this refund request is still subject for approval based on Google's refund policy. Per our Terms of Service, all sales are final.

**[16:00] [Agent] • Support Specialist:**
**Before we proceed to request for a refund of your membership, I would like to let you know that when a Google One membership is refunded, it's cancelled immediately and you will no longer have access to expanded storage, benefits, and expert support offered by Google One.**

**[16:00] [Agent] • Support Specialist:**
Should I go ahead and process the refund request?

**[16:03] [Subscriber]:**
NO — please DO NOT cancel or terminate my membership! I have 3.5 TB of active Drive/Gmail data and active credits/workflows that must not be interrupted. To be clear: I am NOT asking for a buyer's-remorse cancellation. I am an active Ultra 20x subscriber asking for service-failure compensation (such as a non-cancelling billing credit toward my next cycle, Google One/Play balance credit, or a 1-month billing extension) because Google's own backend bugs falsely burned ~49.5M tokens of my paid quota between Nov 15-20. Cancelling my active storage and wiping my credits punishes me rather than compensating for Google's outage. If Tier-1 tools only allow cancellation-refunds, please DO NOT touch my active plan—instead, please escalate Case `[REDACTED_CASE_ID]` to a Tier-2 Supervisor who can issue a non-cancelling service credit.

**[16:04] [Agent] • Support Specialist:**
Thanks for confirming

**[16:04] [Agent] • Support Specialist:**
Please provide a screenshot that shows the issue you're referring to for us to further investigate it

**[16:05] [Subscriber]:**
one sec

**[16:06] [Agent] • Support Specialist:**
Take your time

**[16:08] [Subscriber]:**
*[Uploaded raw SQLite `gen_metadata` & `steps.error_details` telemetry screenshot]*
I have attached the screenshot of the raw local SQLite billing and error records from Google Antigravity on my Mac (for Case `[REDACTED_CASE_ID]`), showing the exact Google Server ResponseIDs where cached_in dropped to 0 (overbilling ~49.5M uncached tokens), the 64.9% zero-thinking regression, and the 9 consecutive empty failures leading directly into HTTP 429 RESOURCE_EXHAUSTED. Please escalate this evidence to a Tier-2 Billing Specialist / Supervisor for a non-cancelling service credit or billing extension on my active Ultra 20x account.

**[16:09] [Agent] • Support Specialist:**
Thanks for letting me know that

**[16:11] [Agent] • Support Specialist:**
May I know when did the issue started?

**[16:12] [Subscriber]:**
Based strictly on my local Antigravity SQLite logs (baseline starts Nov 12, 2026): - Nov 12–13 (Normal Baseline): 0.0% strict cache failures on Hydrogen High, and only 0.3% (1/337) zero-thinking calls on Argon Medium. - Exact Onset — Nov 15, 2026 at 01:16:38 UTC: Server started returning empty responses that drained quota into HTTP 429 at 01:31:15 UTC, and Hydrogen High 0%-cache failures jumped from 0.0% to 20.8% on Nov 15 (and 40.0% on Nov 16). - Nov 16–19 (Peak): Argon Medium zero-thinking jumped to 25.2% (Nov 16) and 64.9% (Nov 19); on Nov 17 Carbon 0%-cache failures hit 14.7%-50.0% and Hydrogen High silently switched to "gemini-4-hydrogen-tiered-high". - Ongoing Today (Nov 20, 03:51:07 UTC): Still had a 474,739-token 0%-cache overbill on Carbon High (ResponseID `q8P_arKjJ6-F****`).

**[16:13] [Agent] • Support Specialist:**
Thanks for letting me know that

**[16:13] [Agent] • Support Specialist:**
Please allow me 5-10 minutes as I will be consulting this with our higher specialists.

**[16:14] [Subscriber]:**
Thank you, I will stay online right here—please take your time.

**[16:14] [Agent] • Support Specialist:**
You're welcome

**[16:24] [Agent] • Support Specialist:**
Thanks for waiting

**[16:24] [Subscriber]:**
no worries

**[16:27] [Agent] • Support Specialist:**
**May I please know how would you like us to proceed as we can offer you either 2,000 AI credits or a refund of your last plan charge without cancelling your plan?**

**[16:28] [Subscriber]:**
Please proceed with the second option: a full refund of my last plan charge WITHOUT cancelling my plan (keeping my active Google One AI Ultra 20x membership, 30 TB storage, and benefits intact). Could you also confirm the refund amount and send a written confirmation to my email under Case ID `[REDACTED_CASE_ID]` once processed? Thank you so much for your help!

**[16:30] [Agent] • Support Specialist:**
In this matter our higher specialists needs more time to process the request by that I will be sending you an update once I receive an email coming from them.

**[16:30] [Agent] • Support Specialist:**
Is there anything else I can help you with today?

**[16:32] [Subscriber]:**
That covers everything for today—could you please email me a copy of this chat transcript under Case ID `[REDACTED_CASE_ID]`, and let me know the expected timeframe (e.g. 24–48 hours) for the specialist email confirming the non-cancelling refund of my last plan charge? Thank you again!

**[16:34] [Agent] • Support Specialist:**
No worries, you will have an option to have a copy our chat transcript once our chat ends.

**[16:34] [Agent] • Support Specialist:**
We still don't have an exact timeframe when they will update but don't worry as I will send you an email as soon as possible.

**[16:34] [Agent] • Support Specialist:**
Is there anything else I can help you with today?

**[16:36] [Subscriber]:**
Before we end the chat, I need to have this clearly confirmed in writing on Case `[REDACTED_CASE_ID]`:
1. Since you offered me the choice at 16:27 ("either 2,000 AI credits or a refund of your last plan charge without cancelling your plan"), please confirm whether this non-cancelling full refund is ALREADY approved by your higher specialist (and just awaiting payment processing), or still pending approval?
2. Please confirm in your case notes that under NO circumstances will my active Ultra 20x membership or 30 TB storage be cancelled while processing this refund.
3. Could you send a quick initial email from Case `[REDACTED_CASE_ID]` to my inbox right now stating this recorded resolution before we disconnect?

**[16:37] [Agent] • Support Specialist:**
`[REDACTED_NAME]`, please know that the request is still under the review for approval to our higher specialists team and I will send you an email right after our chat ends.

**[16:37] [Agent] • Support Specialist:**
Is there anything else I can help you with today?

---

### Post-Chat Update (Nov 20–21, 2026)
Shortly after the live chat ended, the frontline specialist politely sent a confirmation email under Case ID `[REDACTED_CASE_ID]` confirming that the non-cancelling refund request had been escalated to higher specialists for approval. As of this update, no approval timeline and no final decision/refund have been provided.
