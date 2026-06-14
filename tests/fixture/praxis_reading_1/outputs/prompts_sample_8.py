"""Sample 8 rows from prompts.csv and run cached_batch_call_file on them.

Used for quick end-to-end smoke tests without running the full 56-row set.
Output lands in  outputs_batch_infer_<model>/prompts_sample_8.csv  (and .jsonl).
"""
import sys
from pathlib import Path

import pandas as pd

# Make sure the llm_evals root is importable regardless of cwd.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llm_common.llm_infer.api_info.dataclass_ import GEMINI_API
from llm_common.llm_infer.api_info.dataclass_ import apiconfig_for_model
from llm_common.llm_infer.batch_call import cached_batch_call_file

OUTPUTS_DIR = Path(__file__).resolve().parent
PROMPTS_CSV = OUTPUTS_DIR / "prompts.csv"
SAMPLE_CSV  = OUTPUTS_DIR / "prompts_sample_8.csv"
SAMPLE_SIZE = 8


def build_sample(seed: int = 42) -> Path:
    df = pd.read_csv(PROMPTS_CSV)
    sample = df.sample(n=min(SAMPLE_SIZE, len(df)), random_state=seed)
    sample.to_csv(SAMPLE_CSV, index=False)
    print(f"Sample written: {SAMPLE_CSV}  ({len(sample)} rows)")
    return SAMPLE_CSV


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Sample 8 prompts and run batch inference.")
    parser.add_argument(
        "--model",
        default=GEMINI_API.model,
        help="Model name (must exist in MODEL_TO_APICONFIG). Default: %(default)s",
    )
    parser.add_argument(
        "--max-workers", type=int, default=4,
        help="Parallel workers for cached_batch_call_file. Default: %(default)s",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for sample selection. Default: %(default)s",
    )
    parser.add_argument(
        "--rebuild-sample", action="store_true",
        help="Re-generate prompts_sample_8.csv even if it already exists.",
    )
    args = parser.parse_args()

    if args.rebuild_sample or not SAMPLE_CSV.exists():
        build_sample(seed=args.seed)
    else:
        print(f"Reusing existing sample: {SAMPLE_CSV}")

    apiconfig = apiconfig_for_model(args.model)
    output_path = cached_batch_call_file(
        csv_path=SAMPLE_CSV,
        apiconfig=apiconfig,
        max_workers=args.max_workers,
    )
    print(f"Done → {output_path}")


if __name__ == "__main__":
    main()
