# Architecture

## Flow: one transaction per box

Each box is one transaction. It changes one aggregate, or only rows that a unique key guards. Each arrow between workers is a command in the outbox (D4, D45).

```mermaid
flowchart TB
  subgraph c1["Clerk, through the API"]
    T1["T1 Ingest bill<br/>supplier if new (I2, I3)<br/>bill (I4)"]
    T2["T2 Start check<br/>job: queued<br/>+ outbox CheckBill (I14)"]
  end

  subgraph wc["worker-checks"]
    T3["T3 Check one bill<br/>exceptions (I6)<br/>resolution: system, add or delete (I7)<br/>job: check result, completed? (I13)"]
  end

  BOARD["Job board<br/>progress from Redis, not stored"]

  subgraph c2["Clerk, through the API"]
    T4["T4 Ignore exception<br/>resolution: ignore (I7)"]
    T5["T5 Request proposal<br/>proposal: drafting, quota slot (I12)<br/>+ outbox DraftFixProposal"]
  end

  subgraph wa["worker-propose-ai"]
    T6["T6 Draft<br/>proposal: pending or failed<br/>actions, sync keys (I10)<br/>audit (I15)"]
  end

  subgraph ap["Approver, through the API"]
    T7["T7 Approve<br/>proposal: approved (I9)<br/>resolution: proposal, one per exception (I7)<br/>audit + outbox ApplyFixProposal (I14)"]
    T7r["Reject<br/>proposal: rejected"]
    T10["T10 Retry<br/>proposal: sync_failed to syncing<br/>+ outbox ApplyFixProposal"]
  end

  subgraph wp["worker-apply"]
    T8["T8 Apply<br/>proposal: syncing<br/>per action: call port, then action synced or failed<br/>all synced: proposal synced (I11)<br/>5 failures: sync_failed (D9)"]
  end

  ACC[("Accounting<br/>demo stub in v1")]

  subgraph cb["Accounting, through the REST edge"]
    T9["T9 Signed callback<br/>proposal: action synced (I11)"]
  end

  T1 --> T2
  T2 -- CheckBill --> T3
  T3 -. progress .-> BOARD
  T3 --> T4
  T3 --> T5
  T5 -- DraftFixProposal --> T6
  T6 --> T7
  T6 --> T7r
  T7 -- ApplyFixProposal --> T8
  T10 -- ApplyFixProposal --> T8
  T8 -- "sync key (D8)" --> ACC
  ACC -- "signature (D23)" --> T9
```

Derived on read, never stored: exception status, job failed count, money at risk (D38).

Races that the database stops:

| Race | Guard |
| --- | --- |
| Approve P1 and approve P2, both on E1 | Unique resolution per exception (I7) |
| Approve P1 and ignore E1 | Unique resolution per exception (I7) |
| Approve P1 and re-check that resolves E1 | Unique resolution per exception (I7) |
| A1 and A2 approve P1 | Conditional update `pending` to `approved` (I9) |
| Two callbacks for two actions of P1 | Row lock on P1 (I11) |
| Two workers finish the last two bills of J1 | Row lock on J1 (I13) |
| Two requests take quota slot 50 | Unique tenant, day, slot (I12) |
