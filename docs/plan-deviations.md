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
