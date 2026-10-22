import { graphql } from "../gql";

export const VIEWER = graphql(`
  query Viewer {
    viewer {
      tenantName
      role
    }
  }
`);

export const BILLS = graphql(`
  query Bills {
    bills {
      totalCount
      items {
        id
        supplierName
        invoiceNumber
        amount
        currency
        issueDate
        hasReceipt
        createdAt
      }
    }
  }
`);

export const INGEST_BILL = graphql(`
  mutation IngestBill($idempotencyKey: String!, $bill: BillInput!) {
    ingestBill(idempotencyKey: $idempotencyKey, bill: $bill) {
      billId
    }
  }
`);

export const START_BILL_CHECK = graphql(`
  mutation StartBillCheck($billIds: [UUID!]!) {
    startBillCheck(billIds: $billIds) {
      id
      status
      billCount
      okCount
      failedCount
      seq
      percent
    }
  }
`);

export const CHECK_JOB = graphql(`
  query CheckJob($id: UUID!) {
    checkJob(id: $id) {
      id
      status
      billCount
      okCount
      failedCount
      seq
      percent
    }
  }
`);

// The cache entry that each console event of a check job updates (D47).
export const CHECK_JOB_ROW = graphql(`
  fragment CheckJobRow on CheckJob {
    id
    status
    billCount
    okCount
    failedCount
    seq
    percent
  }
`);

export const EXCEPTIONS = graphql(`
  query Exceptions($status: String, $severity: String) {
    exceptions(status: $status, severity: $severity) {
      totalCount
      items {
        id
        billId
        supplierName
        invoiceNumber
        rule
        severity
        status
        createdAt
        resolvedBy
        reason
      }
    }
  }
`);

export const IGNORE_EXCEPTION = graphql(`
  mutation IgnoreException($exceptionId: UUID!, $reason: String!) {
    ignoreException(exceptionId: $exceptionId, reason: $reason) {
      id
      status
      resolvedBy
      reason
    }
  }
`);

export const REQUEST_FIX_PROPOSAL = graphql(`
  mutation RequestFixProposal($exceptionIds: [UUID!]!) {
    requestFixProposal(exceptionIds: $exceptionIds) {
      id
      status
    }
  }
`);

export const PROPOSALS = graphql(`
  query Proposals($status: String) {
    proposals(status: $status) {
      totalCount
      items {
        id
        status
        requestedBy
        createdAt
        exceptions {
          id
        }
        actions {
          kind
        }
      }
    }
  }
`);

export const PROPOSAL = graphql(`
  query Proposal($id: UUID!) {
    proposal(id: $id) {
      id
      status
      requestedBy
      quotaSlot
      failedReason
      approvedBy
      approvedAt
      rejectReason
      createdAt
      exceptions {
        id
        rule
        invoiceNumber
      }
      actions {
        kind
        billId
        supplierName
        invoiceNumber
        poNumber
        syncKey
        status
        attempts
      }
    }
  }
`);

// Each decision returns the fields that the proposal page shows, so the cache updates the page.
export const APPROVE_FIX_PROPOSAL = graphql(`
  mutation ApproveFixProposal($proposalId: UUID!) {
    approveFixProposal(proposalId: $proposalId) {
      id
      status
      approvedBy
      approvedAt
      rejectReason
    }
  }
`);

export const REJECT_FIX_PROPOSAL = graphql(`
  mutation RejectFixProposal($proposalId: UUID!, $reason: String!) {
    rejectFixProposal(proposalId: $proposalId, reason: $reason) {
      id
      status
      approvedBy
      approvedAt
      rejectReason
    }
  }
`);

export const RETRY_SYNC = graphql(`
  mutation RetrySync($proposalId: UUID!) {
    retrySync(proposalId: $proposalId) {
      id
      status
    }
  }
`);

export const ACCOUNTING_LEDGER = graphql(`
  query AccountingLedger {
    accountingLedger {
      totalCount
      items {
        syncKey
        kind
        supplierName
        invoiceNumber
        poNumber
        answer
        receivedAt
      }
    }
  }
`);

export const SUPPLIERS = graphql(`
  query Suppliers {
    suppliers {
      totalCount
      items {
        id
        name
        vatNumber
      }
    }
  }
`);

export const ADD_PURCHASE_ORDER = graphql(`
  mutation AddPurchaseOrder(
    $poNumber: String!
    $supplierId: UUID!
    $amount: MinorUnits!
    $currency: String!
  ) {
    addPurchaseOrder(
      poNumber: $poNumber
      supplierId: $supplierId
      amount: $amount
      currency: $currency
    ) {
      id
      poNumber
    }
  }
`);
