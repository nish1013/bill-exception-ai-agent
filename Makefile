.PHONY: test-all test-api bench

test-all:
	scripts/test-all.sh

# Local runs keep the test databases between runs. test-all and CI create them from zero.
test-api:
	docker compose exec -T api uv run pytest --reuse-db $(ARGS)

# Prints the median time of startBillCheck with 500 bills. It does not pass or fail on time (D38).
bench:
	docker compose exec -T api uv run python -m benchmarks.start_bill_check
