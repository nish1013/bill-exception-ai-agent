.PHONY: test-all test-api

test-all:
	scripts/test-all.sh

# Local runs keep the test databases between runs. test-all and CI create them from zero.
test-api:
	docker compose exec -T api uv run pytest --reuse-db $(ARGS)
