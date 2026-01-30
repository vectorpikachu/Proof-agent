from __future__ import annotations
from typing import Optional, Any
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

from coqstoq.eval_thms import EvalTheorem
from coqstoq.predefined_projects import VAL_SPLIT, TEST_SPLIT, CUTOFF_SPLIT, MY_TESTS_SPLIT
from coqstoq.create_theorem_lists import load_reference_list
from coqstoq.find_eval_thms import get_eval_thms, get_all_eval_thms, get_eval_thms


class Split(Enum):
    VAL = VAL_SPLIT
    TEST = TEST_SPLIT
    CUTOFF = CUTOFF_SPLIT
    MY_TESTS = MY_TESTS_SPLIT


def num_theorems(split: Split, coqstoq_loc: Path) -> int:
    thm_list = load_reference_list(split.value, coqstoq_loc)
    return len(thm_list)


def get_theorem(split: Split | str, idx: int, coqstoq_loc: Path) -> EvalTheorem:
    from coqstoq.eval_thms import Split as EvalSplit
    if isinstance(split, str):
        split_val = EvalSplit(f"{split}-repos", f"{split}-theorems")
    else:
        split_val = split.value
    thm_list = load_reference_list(split_val, coqstoq_loc)
    thm_ref = thm_list[idx]
    eval_thms = get_eval_thms(coqstoq_loc / thm_ref.thm_path)
    return eval_thms[thm_ref.thm_idx]


def get_theorem_list(split: Split, coqstoq_loc: Path) -> list[EvalTheorem]:
    eval_thm_dict = get_all_eval_thms(split.value, coqstoq_loc)
    thm_list = load_reference_list(split.value, coqstoq_loc)
    eval_thms: list[EvalTheorem] = []
    for thm_ref in thm_list:
        eval_thms.append(eval_thm_dict[thm_ref.thm_path][thm_ref.thm_idx])
    return eval_thms
