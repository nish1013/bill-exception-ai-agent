import statistics
import time

from tests.check_data import add_bill, add_bulk_bills

START = """
mutation($ids: [UUID!]!) { startBillCheck(billIds: $ids) { id billCount } }
"""
TARGET_MS = 500
RUNS = 5


def test_us5_500_bills_median_ms(committed_db, graphql, token_for):
    add_bill("K1")
    ids = [str(bill_id) for bill_id in add_bulk_bills(500)]
    token = token_for("c1")

    def start() -> float:
        began = time.perf_counter()
        response = graphql(START, token, {"ids": ids})
        elapsed = (time.perf_counter() - began) * 1000
        assert response.json()["data"]["startBillCheck"]["billCount"] == 500
        return elapsed

    start()
    runs = [start() for _ in range(RUNS)]

    median = statistics.median(runs)
    print(
        f"\nstartBillCheck, 500 bills: median {median:.0f} ms, target {TARGET_MS} ms, "
        f"runs {', '.join(f'{ms:.0f}' for ms in runs)}"
    )
