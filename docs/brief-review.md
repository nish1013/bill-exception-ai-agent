# Brief review

## 2026-10-21 — review of `docs/brief.md` at `5ff6e68`

All findings are resolved. Decisions D1–D23 in `decisions.md` resolve them.

Severity: High = data loss or wrong state. Medium = wrong history, a stuck entity, or undefined behaviour. Low = an unspecified detail with a safe default.

| ID | Finding | Severity | Status | Resolved by |
|---|---|---|---|---|
| F1 | The brief does not define a duplicate bill. A loose rule flags valid bills, and a strict rule misses `INV-001` vs `inv 001`. | High | Resolved | D1 |
| F2 | The brief does not separate an ingest retry from a duplicate bill. A client retry raises a false duplicate exception. | High | Resolved | D2 |
| F3 | The brief has no source for purchase orders. The PO-mismatch check has no data, and PO is not in the domain. | Medium | Resolved | D3 |
| F4 | A crash after the job row commits and before the enqueue leaves the job `queued` with no work and no signal. | Medium | Resolved | D4 |
| F5 | Two check jobs on one bill, or a re-check, raise the same exception twice. Counts and money at risk double. | High | Resolved | D5 |
| F6 | The brief does not say what happens to an open exception when a re-check no longer finds it. It stays open and stale. | Medium | Resolved | D6 |
| F7 | A proposal can become stale between draft and approve. An approve then applies a plan made for old data. | High | Resolved | D7 |
| F8 | Two concurrent approves, or an at-least-once apply delivery, can send the same action to accounting twice. | High | Resolved | D8 |
| F9 | The brief has no apply state after retries run out. The approved proposal stays stuck and nobody sees it. | Medium | Resolved | D9 |
| F10 | The brief does not say when an exception becomes `resolved`: on approve or on sync. The report shows wrong money at risk. | Medium | Resolved | D10 |
| F11 | The brief does not name who can approve, or if a requester can approve their own proposal. One user can control the full money path. | High | Resolved | D11 |
| F12 | The brief does not say how tenant isolation is enforced. One missing filter leaks rows, and workers have no request context. | High | Resolved | D12 |
| F13 | The brief does not define money at risk. Sums mix currencies, and a bill with several exceptions counts more than once. | Medium | Resolved | D13 |
| F14 | The brief does not give a money representation. Floats give rounding errors in totals. | Low | Resolved | D14 |
| F15 | The brief does not say where the request tenant comes from. A tenant taken from a request argument lets a user read another tenant. | High | Resolved | D15 |
| F16 | The brief does not say what one failed bill does to a batch job. One bad bill can fail all the others. | Medium | Resolved | D16 |
| F17 | The brief does not say what happens to a message that always fails. It retries forever and blocks the queue. | Medium | Resolved | D17 |
| F18 | The brief does not name the source of truth for job state. Redis loses progress on restart, and the console shows a wrong state. | Medium | Resolved | D18 |
| F19 | Progress events can arrive out of order. The console can show progress go back. | Low | Resolved | D19 |
| F20 | The brief does not bound the agent loop. A loop can run without end and use the full quota. | Medium | Resolved | D20 |
| F21 | The brief does not say what the proposal quota counts. | Low | Resolved | D21 |
| F22 | The brief does not define supplier identity. The same supplier registered twice hides duplicate bills across the two records. | Medium | Resolved | D22 |
| F23 | The brief does not say how webhooks and sync callbacks are authenticated. A forged callback can change sync state. | High | Resolved | D23 |
