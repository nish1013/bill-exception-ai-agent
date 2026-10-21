# Plan deviations

Where the build departs from [plan.md](plan.md), and why. A deviation becomes a decision only once it is added to [decisions.md](decisions.md).

## D1. CI gets its services from Compose (PR 1, 2026-10-21)

In short: CI starts Postgres, Redis and RabbitMQ with Docker Compose, the same way as a local run.

Plan:     The Stack table, row CI, gives "GitHub Actions, Postgres, Redis and RabbitMQ as services". PR 1 and D56 say that CI calls `make test-all`.
Built:    The CI job has no `services:` block. It runs `make test-all`, which starts the full Compose stack on the runner.
Why:      `scripts/test-all.sh` runs `docker compose up --wait` and runs the tests in the `api` container. Service containers in the job would duplicate the stack and give CI a second, different set of services.
Undo:     Add a `services:` block to `.github/workflows/ci.yml` and a CI-only test path that does not start Compose. Local and CI runs then differ, which D56 forbids.

## D2. GraphQL has one `viewer` query in PR 2 (PR 2, 2026-10-21)

In short: The API has a `viewer` query. It returns the tenant id, the tenant name and the role of the token.

Plan:     The API section lists the queries `bills`, `exceptions`, `checkJob`, `proposals`, `proposal` and `report`. It lists no query that returns the signed-in user.
Built:    `query { viewer { tenantId tenantName role } }`. The tenant name comes from the `tenant` row, read through row-level security.
Why:      Graphene refuses a schema with no query field, and each planned query reads a table that a later PR adds. US1 rows 1 and 4 need a response that shows the tenant of the request. The tenant name shows that the database session runs for the same tenant.
Undo:     Remove `viewer` from `apps/api/payables/entrypoints/graphql/schema.py` after PR 3 adds `bills`. Move the US1 tests to `bills`.

## D3. US1 row 3 runs on the tenant table in PR 2 (PR 2, 2026-10-21)

In short: The test for "C1 queries bill B9 of T2 by id" reads tenant `T2` by id. The bill version of the test waits for the bill table.

Plan:     PR 2 is accepted when each US1 row passes. Row 3 queries bill `B9` of tenant `T2` by id and expects not found.
Built:    `test_us1_t2_row_by_id_not_found_for_t1` reads the `tenant` row of `T2` by id in a `T1` transaction and gets no row. The `bill` table and a bill query come in PR 3.
Why:      `tenant` is the only table in PR 2. The same row-level security policy filters both lookups. With row-level security turned off on `tenant`, the test fails.
Undo:     Add a GraphQL test for bill `B9` by id in PR 3. Delete the tenant version.

## D4. An error with no mapping returns `INTERNAL` (PR 2, 2026-10-21)

In short: A resolver error with no mapping returns code `INTERNAL`, status 500 and the message "Internal error".

Plan:     The "Validation and responses" table lists 400, 401, 403, 404, 409, 422 and 429. It has no row for an error with no mapping.
Built:    The error mapper logs the error and returns `extensions.code = INTERNAL` and `extensions.status = 500`. The original message stays out of the response.
Why:      Graphene returns the text of each exception by default. That text can hold SQL and row values.
Undo:     Remove the `INTERNAL` branch in `apps/api/payables/entrypoints/graphql/error_mapper.py`. Graphene then returns the original message.

## D5. `addPurchaseOrder` takes the currency as its own argument (PR 3, 2026-10-21)

In short: A PO amount is two arguments: `amount` in minor units and `currency`. The bill input has the same two fields.

Plan:     The API table gives `addPurchaseOrder(poNumber, supplierId, amount)`. The Money value object needs integer minor units and an ISO 4217 code (D14).
Built:    `addPurchaseOrder(poNumber, supplierId, amount: MinorUnits!, currency: String!)`. `MinorUnits` is a scalar that passes any number to `Money`. `Money` refuses a float with status 400.
Why:      US3 rows 1 and 4 give a currency for each PO, and `amount` alone carries no currency. With the GraphQL `Int` type, `amount: 1200.50` fails in the document parse and the error has no `extensions.status` (D48).
Undo:     Replace `amount` and `currency` with one `MoneyInput` object in `apps/api/payables/entrypoints/graphql/mutation.py` and `bill_input.py`.

## D6. Money refuses a negative amount (PR 3, 2026-10-21)

In short: An amount below 0 minor units returns status 400. A `CHECK` on each amount column refuses it in the database too.

Plan:     The value-object table gives `Money` as integer minor units and an ISO 4217 code. It gives no lower limit.
Built:    `Money` accepts 0 to 2^63 - 1 minor units. The `bill` and `purchase_order` tables have `CHECK (amount_minor >= 0)`, and `bill` has the same check on `vat_amount_minor`.
Why:      A negative bill is a credit note, and v1 has no credit-note story. A negative amount would lower the money at risk total (D13). The upper limit is the range of the `bigint` column.
Undo:     Remove the lower limit in `apps/api/payables/domain/money.py` and drop the `*_not_negative` constraints with a new migration.
