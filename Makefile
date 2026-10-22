.PHONY: test-all test-api test-openai bench

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
