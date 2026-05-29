"""Find the rows a model failed to answer in a scored batch-infer CSV.

A row is "failed" when `pred` is empty: the model's reasoning was truncated
(no closing </think>, so no final letter could be extracted) — these are the
`failed` count in the report (total - successful), neither successful nor correct.

Usage:
    python find_failed.py [--model Qwen3-32B]
"""

import argparse
import os
from pathlib import Path

import pandas as pd

PRAXIS_DIR = Path(f"{os.environ['HOME']}/klee_code/git_repos/parse_evaluation/praxis_reading_1")


def find_failed(model: str) -> pd.DataFrame:
    scored_path = PRAXIS_DIR / f"outputs_batch_infer_{model}" / "prompts_scored.csv"
    df = pd.read_csv(scored_path)
    failed = df[df["pred"].isna()]

    print(f"model: {model}")
    print(f"scored file: {scored_path}")
    print(f"failed (no answer extracted): {len(failed)} / {len(df)}")
    print(f"failed ids: {list(failed['id'])}")
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen3-32B")
    args = parser.parse_args()
    find_failed(args.model)


if __name__ == "__main__":
    main()
