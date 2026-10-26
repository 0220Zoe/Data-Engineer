"""Check that each verified query's operation call returns the known-correct answer."""
from pathlib import Path

import duckdb
import yaml

from src import sample_data
from src.gateway import Gateway


def run(con=None) -> list[tuple[str, bool]]:
    con = con or duckdb.connect()
    sample_data.build(con)
    gateway = Gateway(con)
    cases = yaml.safe_load((Path(__file__).parent / "verified_queries.yaml").read_text())
    results = []
    for case in cases:
        got = gateway.call(case["operation"], case["params"], caller="eval", role="assistant")
        expected = con.execute(case["expect_sql"]).fetchall()
        n = len(expected[0])
        passed = [tuple(r[:n]) for r in got.rows] == [tuple(r) for r in expected]
        results.append((case["question"], passed))
    return results


if __name__ == "__main__":
    results = run()
    for question, passed in results:
        print(("PASS" if passed else "FAIL"), question)
    print(f"{sum(p for _, p in results)}/{len(results)} verified queries passed")
