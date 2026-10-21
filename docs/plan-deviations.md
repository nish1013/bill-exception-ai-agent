# Plan deviations

Where the build departs from [plan.md](plan.md), and why. A deviation becomes a decision only once it is added to [decisions.md](decisions.md).

## D1. CI gets its services from Compose (PR 1, 2026-10-21)

In short: CI starts Postgres, Redis and RabbitMQ with Docker Compose, the same way as a local run.

Plan:     The Stack table, row CI, gives "GitHub Actions, Postgres, Redis and RabbitMQ as services". PR 1 and D56 say that CI calls `make test-all`.
Built:    The CI job has no `services:` block. It runs `make test-all`, which starts the full Compose stack on the runner.
Why:      `scripts/test-all.sh` runs `docker compose up --wait` and runs the tests in the `api` container. Service containers in the job would duplicate the stack and give CI a second, different set of services.
Undo:     Add a `services:` block to `.github/workflows/ci.yml` and a CI-only test path that does not start Compose. Local and CI runs then differ, which D56 forbids.
