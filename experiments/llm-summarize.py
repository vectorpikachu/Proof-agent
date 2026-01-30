#!/usr/bin/env python3
"""
LLM Summarizer for analyzing agent failure reasons from JSON trajectories.

This script reads JSON files from an experimental summaries folder and uses
an LLM to analyze why the agent failed on each theorem.
"""

import sys
from functools import partial

if __name__ == "__main__":
    sys.path[0] = "/home/user/PLResearch/coq-agent-branch-dev"

import json
import argparse
from prompt.util import str_to_model
from pathlib import Path
from typing import Dict, List, Optional
from multiprocessing import Pool
# Add parent directory to path to import from the main codebase
sys.path.insert(0, str(Path(__file__).parent.parent))

from prompt.llm import query_llm_raw
from prompt.util import ChatHistory, ModelHub


def create_analysis_prompt(
    trajectory: str,
    ground_truth: str
) -> ChatHistory:
    """Create a chat history with the analysis prompt for the LLM."""
    
    
    # System message
    system_msg = """You are an expert in formal verification and Coq theorem proving. 
Your task is to analyze agent trajectories (a json file content) where the agent attempted to prove a theorem but failed or success. You are also given the ground truth for reference.
Provide a concise analysis of WHY the agent failed, focusing on the root cause(s).

- READ "progress_part" for new tactics verified at this round.
- READ "verified_before_this_round" for the cumulative tactics verified so far.
- READ "ground_truth" for the ground truth for reference.

Answer the following questions:
- Is any goal or subgoal in the file false, unprovable, semantically incorrect or logically incorrect?
- Is any induction scheme in the file incorrect?
- Is any lemma used incorrectly and in a incorrect shape?
- Other errors: other errors that are not covered by the above questions.

Provide a clear, detailed summary of the failure reason(s).
"""
    
    user_msg = f"""Analyze the following agent trajectory: 
[Trajectory]
{trajectory}
[Ground Truth for Reference]
{ground_truth}
"""

    chat = ChatHistory([
        {'role': 'system', 'content': system_msg},
        {'role': 'user', 'content': user_msg},
    ])

    return chat


def analyze_single_trajectory(
    json_path: Path,
    model: ModelHub,
    output_dir: Optional[Path] = None
):
    
    # Read the trajectory
    with open(json_path, 'r', encoding='utf-8') as f:
        trajectory = f.read().strip()

    with open(json_path.parent.parent / json_path.stem / "stdout.log", "r") as f:
        ground_truth = f.read().strip().split("\n")[3:-1]
        ground_truth = "\n".join([
            line.rstrip() for line in ground_truth if line.strip() != ""
        ])


    if '"success": true' in trajectory:
        print(f"Trajectory {json_path.stem} is successful, skipping analysis")
        return
    
    file_name = json_path.stem
    try:
        result = query_llm_raw(
            msgs=create_analysis_prompt(trajectory, ground_truth).dump(),
            mod=model,
            cfg={},
            save_name=None
        )[1]
        
        analysis_text = result.message.content
                
        
        # Save individual analysis if output directory is provided
        if output_dir:
            output_file = output_dir / f"{file_name}_analysis.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Analysis:\n\n{analysis_text}\n")
            print(f"Saved analysis to: {output_file}")
        
        
    except Exception as e:
        print(f"Error analyzing {file_name}: {e}")
        import traceback
        traceback.print_exc()
        
def analyze_wrapper(model, output_dir, json_file):
    return analyze_single_trajectory(json_file, model, output_dir)

def batch_analyze(
    summaries_dir: Path,
    output_dir: Path,
    model_name: str = 'GPT5',
    limit: Optional[int] = None,
    workers: int = 4
):
    """Analyze all JSON trajectories in a summaries directory."""
    
    print(f"Analyzing trajectories from: {summaries_dir}")
    print(f"Output directory: {output_dir}")
    
    # Create output directory
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Find all JSON files
    json_files = sorted(summaries_dir.glob("*.json"))
    
    if not json_files:
        print(f"No JSON files found in {summaries_dir}")
        return
    
    print(f"Found {len(json_files)} trajectory files")
    
    if limit is not None:
        json_files = json_files[:limit]
        print(f"Processing first {limit} files")
    
    # Initialize model
    model = str_to_model(model_name)
    unary = partial(analyze_wrapper, model, output_dir)

    with Pool(workers) as p:
        p.map(unary, json_files)

def main(): 
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Use LLM to analyze agent failure reasons from trajectory summaries"
    )
    parser.add_argument(
        "--summaries-dir",
        type=Path,
        help="Path to the summaries directory containing JSON trajectory files"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=None,
        help="Output directory for analyses (default: summaries_dir/llm_analyses)"
    )
    parser.add_argument(
        "-m", "--model-name",
        type=str,
        default="GPT5",
        help="Model to use for analysis (default: GPT5)"
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=None,
        help="Limit number of files to process (for testing)"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=4,
        help="Number of workers to use for analysis (default: 4)"
    )
    parser.add_argument(
        "--single-benchmark",
        type=str,
        default=None,
        help="Process a single benchmark (for testing)"
    )
    
    args = parser.parse_args()
    
    if not args.summaries_dir.exists():
        print(f"Error: {args.summaries_dir} does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not args.summaries_dir.is_dir():
        print(f"Error: {args.summaries_dir} is not a directory", file=sys.stderr)
        sys.exit(1)
    
    # Set output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = args.summaries_dir / "llm_analyses"
    
    if args.single_benchmark is not None:
        json_file = args.summaries_dir / f"{args.single_benchmark}.json"
        analyze_wrapper(
            model=str_to_model(args.model_name),
            output_dir=output_dir,
            json_file=json_file
        )
    else:    
        batch_analyze(
            summaries_dir=args.summaries_dir,
            output_dir=output_dir,
            model_name=args.model_name,
            limit=args.limit,
            workers=args.workers
        )

if __name__ == "__main__":
    main()

