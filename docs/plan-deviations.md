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

## D7. The relay and the sweeper read all tenants as a narrow relay role (PR 4, 2026-10-21)

In short: The outbox relay and the search for stale jobs connect as `payables_relay`, a role that bypasses row-level security and has grants on two tables only.

Plan:     The domain contract says that each transaction runs `SET LOCAL app.tenant_id`, and that row-level security filters each table (D12). It gives no database role for the relay or the sweeper.
Built:    Migration `0004_relay_role` creates `payables_relay` with `BYPASSRLS` and `NOSUPERUSER`, and grants only `SELECT, UPDATE, DELETE` on `outbox` and `SELECT` on `check_job`. The sweeper finds stale jobs as this role, then re-enqueues each job in a tenant transaction as the app role.
Why:      One relay publishes the messages of all tenants, and a transaction runs for one tenant only. The owner role can change the schema and passes each policy, which is too wide for a long-running process. The delete right removes sent rows after 7 days (D43).
Undo:     Point the `relay` database alias in `apps/api/config/settings.py` back to the owner role, and drop the role with a new migration.

## D8. A check result row has its own id (PR 4, 2026-10-21)

In short: `check_job_bill` has an `id` primary key and a unique key on `(job_id, bill_id)`.

Plan:     The data model in `domain.md` gives `check_job_bill` the primary key `(job_id, bill_id)`.
Built:    `id` is a `bigint` identity primary key. The unique key `check_job_bill_job_bill_key` on `(job_id, bill_id)` refuses a second result row for one job and bill.
Why:      Django 5.1 has no composite primary key. The unique key gives the same guard that D42 needs for a repeat `CheckBill`.
Undo:     Upgrade to Django 5.2, use `CompositePrimaryKey("job", "bill")` in `apps/api/payables/adapters/orm/check_job_bill.py`, and add a migration.

## D9. A duplicate exception refers to the first earlier bill (PR 4, 2026-10-21)

In short: Each rule gives at most one exception on a bill. The exception refers to the first bill that it repeats, in ingest order.

Plan:     The fingerprint of a `duplicate` exception is "the other bill's id". The plan does not say which bill when a bill repeats two earlier bills, and it does not define "newer".
Built:    "Earlier" means an earlier ingest time, then a lower bill id. With B1, B2 and B3 for `INV001`, B2 and B3 each get one `duplicate` exception that refers to B1. `possible_duplicate` uses the same choice.
Why:      A third copy of a bill is one problem, so the inbox shows it once. The product sets the ingest time, but the supplier sets the issue date, and two bills can share one. Bills never change, so a re-check finds the same first bill and the same fingerprint (I6).
Undo:     Return one finding for each earlier match in `apps/api/payables/domain/checks/duplicate_rules.py`.

## D10. A check waits at most 5 s on a lock (PR 4, 2026-10-21)

In short: Each `CheckBill` transaction sets `lock_timeout` to 5 s. A longer wait fails the attempt, and the task tries again.

Plan:     The worker table gives `worker-checks` a time limit of 30 s for each bill. It gives no limit for a lock wait.
Built:    `CHECK_LOCK_TIMEOUT_MS`, default 5000, sets `lock_timeout` in the task transaction. The task has a soft time limit of 30 s and a hard limit of 40 s. The third failure marks the bill `failed` and sends the message to `checks.dlq` (D17).
Why:      A check waits only behind another check of the same bill or job, and that wait takes milliseconds. A wait of more than 5 s means that a transaction is stuck. The retry frees the worker for other bills.
Undo:     Remove the `lock_timeout_ms` argument in `apps/api/payables/entrypoints/tasks/check_bill.py`. The 30 s soft time limit then ends a long wait.

## D11. Two US6 rows wait for the resolution table in PR 6 (PR 4, 2026-10-21)

In short: The US6 rows "E1 stays `ignored`" and "E1 is `resolved` by `system`" are built in PR 6, not in PR 4.

Plan:     PR 4 is accepted when "the US5 and US6 duplicate rows pass". PR 6 builds the `resolution` table, `ignoreException` and the system resolve (D6).
Built:    PR 4 builds and tests the other US6 rows for `duplicate` and `possible_duplicate`. Each exception is `open`, because no resolution exists yet (D38).
Why:      An ignore and a system resolve are each a `resolution` row (D35). The table and its key on the exception id are the I7 guard that PR 6 builds and tests.
Undo:     None. PR 6 adds the two rows as tests.

## D12. The inbox orders by severity from PR 5 (PR 5, 2026-10-21)

In short: The `exceptions` query gives the severity of each exception and lists high severity first. The inbox shows the rule and the severity.

Plan:     PR 6 lists "severity (D27)" and the console "rule and severity columns". PR 5 delivers US8, and US8 row 1 lists the open exceptions "high severity first".
Built:    `payables/domain/checks/severity.py` holds the fixed map of D27. The query orders high, medium, low, then the newest first. The inbox has a rule column, a severity column and a severity filter.
Why:      US8 row 1 cannot pass with no severity. D27 gives each rule one fixed severity, so the map needs no table or data from PR 6.
Undo:     Remove the severity order in `apps/api/payables/adapters/orm/inbox_query.py` and the two columns in `web/src/inbox/InboxPage.tsx`. PR 6 then adds them.

## D13. US8 row 1 is tested with open exceptions only (PR 5, 2026-10-21)

In short: The status filter accepts each status. With no resolution row, each exception is `open`, so the other statuses return an empty list.

Plan:     US8 row 1 is "`T1` has 3 `open` and 2 `resolved` exceptions", and the list holds the 3 `open` ones. PR 6 builds the `resolution` table.
Built:    `test_us8_open_list_high_severity_first` uses open exceptions only. `test_us8_no_resolution_lists_none_as_closed` shows that `ignored`, `resolved` and `pending_sync` return an empty list.
Why:      A resolved exception is an exception with a resolution row, and its status is derived on read (D35, D38). The table and its key are the I7 guard that PR 6 builds and tests, as in D11.
Undo:     None. PR 6 adds the 2 resolved exceptions to the US8 test.

## D14. PR 5 seeds the two demo tenants (PR 5, 2026-10-21)

In short: `python manage.py seed_demo` creates tenant `T1` Acme Foods and tenant `T2` Beta Bakery. `make test-all` runs it after the migration.

Plan:     The `make test-all` sequence has a "seed demo" step. PR 13 builds `make demo` and the seed of suppliers, POs and bills (D55).
Built:    `seed_demo` inserts the two tenant rows as the owner role, with `ON CONFLICT (id) DO NOTHING`. It inserts no supplier, PO or bill.
Why:      The Playwright specs ingest bills in the Compose database, and each bill needs its tenant row. Tenants are created outside the product (US1), so no mutation creates them.
Undo:     Delete `apps/api/payables/management/commands/seed_demo.py` and its line in `scripts/test-all.sh`. The Playwright specs then fail at the first ingest.

## D15. The bill list and the inbox return at most 500 rows (PR 5, 2026-10-21)

In short: The `bills` and `exceptions` queries return the newest 500 rows. A tenant with more rows does not see the older ones in the console.

Plan:     The Stack table gives the DataGrid free tier for "sort, filter and page" with no extra code. The API section gives no limit and no paging for `bills` or `exceptions`.
Built:    `LIST_LIMIT = 500` in `bill_list_query.py` and `inbox_query.py`. The DataGrid pages the rows in the browser, 25 rows per page.
Why:      The free DataGrid pages in the browser, so the API sends the full list in one response. A fixed limit keeps one response bounded. 500 is also the maximum number of bills in one check job (US5).
Undo:     Remove `LIST_LIMIT` and the slice in `apps/api/payables/adapters/orm/bill_list_query.py` and `inbox_query.py`.
