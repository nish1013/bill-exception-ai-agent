.PHONY: demo test-all test-api test-openai bench

# Starts the stack and seeds two tenants with bills that raise each rule (D55). Safe to run again.
demo:
	docker compose up -d --build --wait
	docker compose exec -T api uv run python manage.py migrate --database owner --noinput
	docker compose exec -T api uv run python manage.py seed_demo
	@echo "Console: http://localhost:$${WEB_PORT:-3000}"
	@echo "Users:   C1 clerk, A1 approver, A2 approver (Acme Foods); C9 clerk (Beta Bakery)"

test-all:
	scripts/test-all.sh

# Local runs keep the test databases between runs. test-all and CI create them from zero.
test-api:
	docker compose exec -T api uv run pytest --reuse-db $(ARGS)

# One live draft with the real model. Only worker-propose-ai holds OPENAI_API_KEY (D54).
test-openai:
	docker compose exec -T worker-propose-ai uv run pytest -m openai -n 0 -rs

# Prints the median time of startBillCheck with 500 bills. It does not pass or fail on time (D38).
bench:
	docker compose exec -T api uv run python -m benchmarks.start_bill_check
