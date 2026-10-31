"""Compare independently run R/SAS logistic results with the Python reference.

Run from repository root: python r/compare_outputs.py --engine r
Missing engine outputs fail with an actionable message; they are never fabricated.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def rows(path):
    if not path.exists():
        raise SystemExit(f"Missing {path}: run that engine first; parity is not verified.")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def term_name(term):
    return "intercept" if term.lower() in {"const", "intercept", "(intercept)"} else term


def unique_map(records, key, value):
    result = {}
    for row in records:
        name = term_name(row[key]) if key == "term" else row[key]
        if name in result:
            raise SystemExit(f"Duplicate key: {name}")
        result[name] = float(row[value])
        if not math.isfinite(result[name]):
            raise SystemExit(f"Non-finite value for {name}")
    return result


def compare(left, right, tolerance, label):
    if left.keys() != right.keys():
        raise SystemExit(f"FAIL {label}: key sets differ; missing={left.keys()-right.keys()}, extra={right.keys()-left.keys()}")
    if not left:
        raise SystemExit(f"FAIL {label}: no records")
    maximum = max(abs(left[k] - right[k]) for k in left)
    print(f"{label}: {len(left):,} keys, max absolute difference={maximum:.10g}, tolerance={tolerance:g}")
    if maximum > tolerance:
        raise SystemExit(f"FAIL {label}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["r", "sas"], required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    reference = args.root / "outputs"
    engine = reference / args.engine
    compare(unique_map(rows(reference / "coefficients.csv"), "term", "coefficient"),
            unique_map(rows(engine / "logistic_coefficients.csv"), "term", "coefficient"), 1e-5, "Coefficients")
    compare(unique_map(rows(reference / "test_predictions.csv"), "borrower_id", "pd_logistic"),
            unique_map(rows(engine / "predictions.csv"), "borrower_id", "pd_logistic"), 1e-6, "Test probabilities")
    print("PASS: logistic coefficient and test-score parity only. This does not verify other engine outputs.")


if __name__ == "__main__":
    main()
