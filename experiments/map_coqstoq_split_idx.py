import argparse
import glob
import json
import os
from typing import Dict, List, Tuple

# This script maps entries in the matched json to (split, idx) in CoqStoq datasets.
# It builds a key using repo_name, file_path, and theorem_content text to join.

def load_metadata(glob_pattern: str) -> Dict[Tuple[str, str, str], Tuple[str, int]]:
    index: Dict[Tuple[str, str, str], Tuple[str, int]] = {}
    for meta_file in glob.glob(glob_pattern):
        # Expect path like .../dataset_<split>/metadata.jsonl
        base = os.path.basename(os.path.dirname(meta_file))
        split = base.replace("dataset_", "")
        with open(meta_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                key = (
                    obj["repo_name"],
                    obj["file_path"],
                    obj["theorem_content"].strip(),
                )
                # Only keep first occurrence; if duplicates exist, they are likely identical
                index.setdefault(key, (split, obj["idx"]))
    return index


def map_entries(matched_path: str, meta_index: Dict[Tuple[str, str, str], Tuple[str, int]]):
    with open(matched_path, "r", encoding="utf-8") as f:
        matched = json.load(f)

    mapped: List[dict] = []
    missed: List[dict] = []
    for e in matched:
        key = (
            e["coqstoq_repo_name"],
            e["coqstoq_file_path"],
            e["coqstoq_theorem_content"].strip(),
        )
        if key in meta_index:
            split, idx = meta_index[key]
            mapped.append({
                "theorem_name": e.get("theorem_name"),
                "coqstoq_idx": e.get("coqstoq_idx"),
                "coqstoq_sp": e.get("coqstoq_sp"),
                "coqstoq_repo_name": e.get("coqstoq_repo_name"),
                "coqstoq_file_path": e.get("coqstoq_file_path"),
                "split": split,
                "idx": idx,
            })
        else:
            missed.append(e)
    return mapped, missed


def main():
    parser = argparse.ArgumentParser(description="Map cobblestone-coqstoq matched entries to (split, idx)")
    parser.add_argument(
        "--matched",
        default="/home/lhz/PLResearch/coq-agent-branch-dense/experiments/cobblestone-inter-coqstoq-matched.json",
        help="Path to matched json",
    )
    parser.add_argument(
        "--meta-glob",
        default="/home/lhz/PLResearch/CoqStoq/datasets/dataset_*/metadata.jsonl",
        help="Glob for CoqStoq metadata jsonl files",
    )
    parser.add_argument(
        "--out",
        default="/home/lhz/PLResearch/coq-agent-branch-dense/experiments/cobb_coqstoq_to_split_idx.json",
        help="Output json path",
    )
    args = parser.parse_args()

    meta_index = load_metadata(args.meta_glob)
    mapped, missed = map_entries(args.matched, meta_index)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(mapped, f, ensure_ascii=False, indent=2)

    print(f"mapped: {len(mapped)}; missed: {len(missed)}")
    if missed:
        miss_path = args.out + ".missed.json"
        with open(miss_path, "w", encoding="utf-8") as f:
            json.dump(missed, f, ensure_ascii=False, indent=2)
        print(f"missed entries written to {miss_path}")


if __name__ == "__main__":
    main()
