#!/usr/bin/env python3
"""
Summarizer script for analyzing runtime logs from coq-agent experiments.

For each "Starting Round: ", summarizes what happened in that round:
- If it is an induction evaluation, returns the evaluation result
- If it is a successful hammer call, returns the hammer tactic
- If it is an LLM call, returns the Goal and the tactic generated
"""

import re
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class InductionEvaluation:
    """Represents an induction evaluation result."""
    reasonable: bool
    reason: str
    suggestion: str


@dataclass
class DestructEvaluation:
    """Represents a destruct evaluation result."""
    is_effective: bool
    needs_induction: bool
    reason: str
    suggestion: str


@dataclass
class ProvabilityEvaluation:
    """Represents a provability evaluation result."""
    provable: bool
    uncertain: bool
    reason: str
    suggestion: str


@dataclass
class HammerCall:
    """Represents a successful hammer call."""
    tactic: str


@dataclass
class LLMCall:
    """Represents an LLM call with goal and generated tactic."""
    goal: str
    tactic: Optional[str]
    invalid_info: Optional[str]


@dataclass
class RoundSummary:
    """Summary of what happened in a round."""
    round_num: int
    induction_eval: Optional[InductionEvaluation] = None
    destruct_eval: Optional[DestructEvaluation] = None
    provability_eval: Optional[ProvabilityEvaluation] = None
    hammer_call: Optional[HammerCall] = None
    llm_call: Optional[LLMCall] = None
    generated_proof: Optional[str] = None
    progress_part: Optional[str] = None
    success: bool = False

def parse_runtime_log(log_path: Path) -> List[RoundSummary]:
    """Parse the runtime.log file and extract round summaries."""
    
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Get the log directory (parent of runtime.log)
    log_dir = log_path.parent
    last_verified = ""
    has_provability_eval = False
    success = 'False'
    
    rounds = content.split('Starting Round')[1:]
    summaries = []
    for current_round, round_content in enumerate(rounds):
        current_summary = RoundSummary(round_num=current_round)

        if "No error found, returning ftext" in round_content:
            current_summary.success = True
            success = 'True'
        
        # Check for induction evaluation
        if 'Induction evaluation:' in round_content:
            induction_eval = parse_induction_eval(round_content, current_round)
            if induction_eval:
                current_summary.induction_eval = induction_eval
        
        # Check for destruct evaluation
        if 'Destruct evaluation:' in round_content:
            destruct_eval = parse_destruct_eval(round_content, current_round)
            if destruct_eval:
                current_summary.destruct_eval = destruct_eval
        
        # Check for provability evaluation
        if 'Provability evaluation:' in round_content:
            provability_eval = parse_provability_eval(round_content, current_round)
            if provability_eval:
                current_summary.provability_eval = provability_eval
                has_provability_eval = True
        
        # Check for successful hammer call
        if 'Hammer worked, continuing' in round_content:
            hammer_call = parse_new_tactic(round_content, current_round)
            if hammer_call:
                current_summary.hammer_call = hammer_call
        
        # Check for LLM call
        certified_file = log_dir / "cfiles" / f"certifed_{current_round}.v"
        if certified_file.exists():
            with open(certified_file, "r") as f:
                current_summary.generated_proof = f.read()
                current_summary.progress_part = current_summary.generated_proof[len(last_verified) - 1:].strip()
                last_verified = current_summary.generated_proof
        else:
            current_summary.generated_proof = last_verified
            current_summary.progress_part = None
        if 'We are going to create prompt info' in round_content:
            llm_call, _ = parse_llm_call(
                round_content, current_round, log_dir
            )
            if llm_call:
                current_summary.llm_call = llm_call
        
        summaries.append(current_summary)
    if has_provability_eval:
        _, sp, num = log_path.parent.name.split('_')
        print('({sp}, {num}),'.format(sp=sp, num=num, success=success), end=' ')
        
    return summaries


def parse_induction_eval(
    content: str,
    round_num: int
) -> Optional[InductionEvaluation]:
    """Parse induction evaluation from content."""
    result_match = re.search(
        r'InductionEvalResult\(reasonable=(\w+),\s*reason=(.+?),\s*suggestion=(.+?)\)\s*$', 
        content, 
        re.MULTILINE | re.DOTALL
    )
    if result_match is None:
        return None
    
    reasonable = result_match.group(1).strip() == "True"
    reason = result_match.group(2).strip()
    suggestion = result_match.group(3).strip()
    
    # Clean up reason and suggestion (remove quotes if present)
    reason = reason.strip('`').strip('"').strip("'")
    suggestion = suggestion.strip('`').strip('"').strip("'")
    
    # Remove trailing paren if present
    if suggestion.endswith(')'):
        suggestion = suggestion[:-1]
    
    return InductionEvaluation(
        reasonable=reasonable,
        reason=reason,
        suggestion=suggestion
    )


def parse_destruct_eval(
    content: str,
    round_num: int
) -> Optional[DestructEvaluation]:
    """Parse destruct evaluation from content."""
    result_match = re.search(
        r'DestructEvalResult\(is_effective=(\w+),\s*needs_induction=(\w+),\s*reason=(.+?),\s*suggestion=(.+?)\)\s*$',
        content,
        re.MULTILINE | re.DOTALL
    )
    if result_match is None:
        return None
    
    is_effective = result_match.group(1).strip() == "True"
    needs_induction = result_match.group(2).strip() == "True"
    reason = result_match.group(3).strip()
    suggestion = result_match.group(4).strip()
    
    # Clean up reason and suggestion (remove quotes if present)
    reason = reason.strip('`').strip('"').strip("'")
    suggestion = suggestion.strip('`').strip('"').strip("'")
    
    # Remove trailing paren if present
    if suggestion.endswith(')'):
        suggestion = suggestion[:-1]
    
    return DestructEvaluation(
        is_effective=is_effective,
        needs_induction=needs_induction,
        reason=reason,
        suggestion=suggestion
    )


def parse_provability_eval(
    content: str,
    round_num: int
) -> Optional[ProvabilityEvaluation]:
    """Parse provability evaluation from content."""
    result_match = re.search(
        r'ProvabilityEvalResult\(provable=(\w+),\s*uncertain=(\w+),\s*reason=(.+?),\s*suggestion=(.+?)\)\s*$',
        content,
        re.MULTILINE | re.DOTALL
    )
    if result_match is None:
        return None
    
    provable = result_match.group(1).strip() == "True"
    uncertain = result_match.group(2).strip() == "True"
    reason = result_match.group(3).strip()
    suggestion = result_match.group(4).strip()
    
    # Clean up reason and suggestion (remove quotes if present)
    reason = reason.strip('`').strip('"').strip("'")
    suggestion = suggestion.strip('`').strip('"').strip("'")
    
    # Remove trailing paren if present
    if suggestion.endswith(')'):
        suggestion = suggestion[:-1]
    
    return ProvabilityEvaluation(
        provable=provable,
        uncertain=uncertain,
        reason=reason,
        suggestion=suggestion
    )

    
def parse_new_tactic(content: str, round_num: int) -> Optional[HammerCall]:
    """Parse the new tactic from the content."""
    match = re.search(r'new_tactic = (.+)', content)
    if match is None:
        return None
    return HammerCall(
        tactic=match.group(1).strip()
    )

def parse_llm_call(
    content: str, 
    round_num: int,
    log_dir: Path
) -> Tuple[LLMCall, Optional[str]]:

    """Parse LLM call information from round content."""
    
    # Extract goal
    goal_match = re.search(r'Goal=\s*\n(.+?)(?=\n\n|\nEnd Get Examples)', content, re.DOTALL)
    if goal_match:
        goal = goal_match.group(1).strip()
    else:
        goal = "Goal not found"
    
    # Extract invalid info and tactic if present
    invalid_info = None
    tactic = None
    
    # Check for Invalid Info pattern
    invalid_info_match = re.search(r'Invalid Info:\s*(.+?)(?=\n\n|\nInvalid Tactic:)', content, re.DOTALL)
    if invalid_info_match:
        invalid_info = invalid_info_match.group(1).strip()

    if 'Augmented not found error message:' in content:
        augmented_not_found_match = re.search(r'Augmented not found error message:\s*(.+?)(?=\n\n)', content, re.DOTALL)
        if augmented_not_found_match:
            invalid_info = augmented_not_found_match.group(1).strip()
    
    # Check for Invalid Tactic pattern
    invalid_tactic_match = re.search(r'Invalid Tactic:\s*\n(.+?)(?=\n\n\n|\n2025-)', content, re.DOTALL)
    if invalid_tactic_match:
        tactic = invalid_tactic_match.group(1).strip()
    
    # Check for valid_check error
    if not invalid_info and "valid_check returned:" in content:
        valid_check_match = re.search(r'valid_check returned:\s*(.+?)(?=\n\n)', content, re.DOTALL)
        if valid_check_match:
            invalid_info = valid_check_match.group(1).strip()
    
    # Parse the save_name to extract generated proof file
    generated_proof = None
    save_name_match = re.search(r'save_name = (.+\.md)', content)
    if save_name_match:
        save_name = save_name_match.group(1).strip()
        # Try to read the generated proof from the prompts directory
        proof_file = log_dir / "prompts" / save_name
        if proof_file.exists():
            try:
                with open(proof_file, 'r', encoding='utf-8') as f:
                    proof_content = f.read()
                    # Extract the Coq code block from the markdown
                    coq_matches = re.findall(
                        r'```coq\n(.+?)\n```', proof_content, re.DOTALL
                    )
                    if coq_matches:
                        generated_proof = coq_matches[-1].strip()
                    else:
                        generated_proof = None
            except Exception:
                generated_proof = None
        else:
            generated_proof = None
    
    return (
        LLMCall(
            goal=goal,
            tactic=tactic,
            invalid_info=invalid_info
        ),
        generated_proof
    )


def summary_to_dict(summary: RoundSummary) -> Dict:
    """Convert a RoundSummary to a dictionary for JSON serialization."""
    result: Dict[str, int | Dict | str] = {
        "round_num": summary.round_num,
    }

    result["progress_part"] = summary.progress_part or ""

    if summary.generated_proof is not None:
        result["verified_before_this_round"] = summary.generated_proof
    
    if summary.induction_eval is not None:
        result["induction_eval"] = asdict(summary.induction_eval)
    
    if summary.destruct_eval is not None:
        result["destruct_eval"] = asdict(summary.destruct_eval)
    
    if summary.provability_eval is not None:
        result["provability_eval"] = asdict(summary.provability_eval)
    
    if summary.hammer_call is not None:
        result["hammer_call"] = asdict(summary.hammer_call)
    
    if summary.llm_call is not None:
        result["proof_prompt"] = asdict(summary.llm_call)

    result["success"] = summary.success
    return result


def process_single_log(log_dir: Path, output_path: Optional[Path] = None):
    """Process a single log directory and output JSON summary."""
    log_path = log_dir / "runtime.log"
    
    if not log_path.exists():
        # print(f"Error: {log_path} not found", file=sys.stderr)
        return False
    
    # print(f"Parsing {log_path}...", file=sys.stderr)
    summaries = parse_runtime_log(log_path)
    
    # print(f"Found {len(summaries)} rounds", file=sys.stderr)
    
    # Convert all summaries to dictionaries
    summaries_dict = [summary_to_dict(s) for s in summaries]
    
    # Output
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summaries_dict, f, indent=4, ensure_ascii=False)
            # print("", file=f)  # Add newline at end
        # print(f"Summary written to {output_path}", file=sys.stderr)
    else:
        json.dump(summaries_dict, sys.stdout, indent=4, ensure_ascii=False)
        # print("")  # Add newline at end
    
    return True


def process_batch(batch_dir: Path):
    """Process all log directories in a batch directory."""
    # Create summaries directory
    summaries_dir = batch_dir / "summaries"
    summaries_dir.mkdir(exist_ok=True)
    # print(f"Created summaries directory: {summaries_dir}", file=sys.stderr)
    
    # Find all subdirectories that contain runtime.log
    log_dirs = []
    for item in batch_dir.iterdir():
        if item.is_dir() and item.name != "summaries":
            runtime_log = item / "runtime.log"
            if runtime_log.exists():
                log_dirs.append(item)
    
    if not log_dirs:
        # print(f"Error: No log directories found in {batch_dir}", file=sys.stderr)
        sys.exit(1)
    
    # print(f"Found {len(log_dirs)} log directories to process", file=sys.stderr)
    
    # Process each log directory
    success_count = 0
    for log_dir in sorted(log_dirs):
        # print(f"\nProcessing {log_dir.name}...", file=sys.stderr)
        output_path = summaries_dir / f"{log_dir.name}.json"
        
        if process_single_log(log_dir, output_path):
            success_count += 1
    
    # print(f"\n{'='*60}", file=sys.stderr)
    # print(f"Batch processing complete: {success_count}/{len(log_dirs)} succeeded", file=sys.stderr)
    # print(f"Summaries saved to: {summaries_dir}", file=sys.stderr)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Summarize runtime logs from coq-agent experiments"
    )
    parser.add_argument(
        "log_dir",
        type=Path,
        help="Path to the log directory (e.g., logfiles_0_79) or batch directory for --batch mode"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output file (default: stdout, ignored in batch mode)"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process all log subdirectories in the given directory"
    )
    
    args = parser.parse_args()
    
    if args.batch:
        # Batch mode: process all subdirectories
        if not args.log_dir.exists():
            # print(f"Error: {args.log_dir} not found", file=sys.stderr)
            sys.exit(1)
        if not args.log_dir.is_dir():
            # print(f"Error: {args.log_dir} is not a directory", file=sys.stderr)
            sys.exit(1)
        process_batch(args.log_dir)
    else:
        # Single directory mode
        if not args.log_dir.exists():
            # print(f"Error: {args.log_dir} not found", file=sys.stderr)
            sys.exit(1)
        success = process_single_log(args.log_dir, args.output)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()

