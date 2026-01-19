import numpy as np
import pandas as pd
import math
import argparse
import sys

def ochiai(coverage, outcomes, stmt_names=None):

    cov = np.asarray(coverage, dtype=int)
    outcomes = np.asarray(outcomes, dtype=int)
    num_tests, num_stmts = cov.shape

    if outcomes.shape[0] != num_tests:
        raise ValueError("Length of outcomes must match number of tests")

    if stmt_names is None:
        stmt_names = [f"stmt_{i}" for i in range(num_stmts)]
    if len(stmt_names) != num_stmts:
        raise ValueError("Length of stmt_names must match number of statements")

    F = int(np.sum(outcomes == 1))
    ef = np.dot(outcomes == 1, cov)
    ep = np.dot(outcomes == 0, cov)

    scores = np.zeros(num_stmts, dtype=float)
    for i in range(num_stmts):
        denom = F * (ef[i] + ep[i])
        if F == 0 or denom == 0:
            scores[i] = 0.0
        else:
            scores[i] = ef[i] / math.sqrt(denom)

    df = pd.DataFrame({
        "stmt": stmt_names,
        "ef": ef,
        "ep": ep,
        "F": [F] * num_stmts,
        "score": scores
    })
    df = df.sort_values(by=["score", "ef", "ep"],
                        ascending=[False, False, True]).reset_index(drop=True)
    df["rank"] = df["score"].rank(method="dense", ascending=False).astype(int)
    return df


def ochiai_from_sets(test_exec_sets, failing_tests, stmt_universe=None):

    n = len(test_exec_sets)
    failures_bool = [False] * n
    if isinstance(failing_tests, (set, list, tuple)) and all(isinstance(x, int) for x in failing_tests):
        for i in failing_tests:
            failures_bool[i] = True
    else:
        failures_bool = [bool(x) for x in failing_tests]

    if stmt_universe is None:
        stmt_universe = sorted({s for executed in test_exec_sets for s in executed})
    stmt_universe = list(stmt_universe)
    idx = {s: i for i, s in enumerate(stmt_universe)}

    cov = np.zeros((n, len(stmt_universe)), dtype=int)
    for t, executed in enumerate(test_exec_sets):
        for s in executed:
            cov[t, idx[s]] = 1
    return ochiai(cov, failures_bool, stmt_names=stmt_universe)

def main_FL():
    parser = argparse.ArgumentParser(description="Ochiai Fault Localization")
    parser.add_argument("--csv", nargs=2, metavar=("COV", "OUT"), help=" ")
    parser.add_argument("--names", type=str, help=" ")
    parser.add_argument("--out", type=str, default="ochiai_results.csv", help=" ")
    args = parser.parse_args()

    if args.csv:
        cov_file, out_file = args.csv
        coverage = pd.read_csv(cov_file, header=None).values
        outcomes = pd.read_csv(out_file, header=None).values.flatten()
        stmt_names = None
        if args.names:
            stmt_names = [line.strip() for line in open(args.names, encoding="utf-8")]
        df = ochiai(coverage, outcomes, stmt_names)
        df.to_csv(args.out, index=False)
        print(f"Results saved to {args.out}")
    else:
        print("Please provide input files with --csv", file=sys.stderr)


