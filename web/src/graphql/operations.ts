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
    }
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
      }
    }
  }
`);
