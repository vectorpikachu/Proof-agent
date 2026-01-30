"""
State management for Coq proof goals and definitions.

This module handles parsing and extracting goal states from Coq proof scripts,
including goal representations, hypothesis management, and definition retrieval.
"""

from coqpyt.coq.proof_file import ProofFile
from coqpyt.coq.structs import Term
from proof.localctx import LocalContext
from logging import Logger, getLogger
from agent.util import pretty_goals
from proof.term import get_names
from coqpyt.coq.proof_file import InvalidFileException
from pathlib import Path
import subprocess
import sys
import os
import re

from env import prover_root, get_output_dir

# Logger
logger = getLogger('ParseStateInternal')

# Constants
DEF_MAX_LIMIT = 4096 - 3
SEARCH_LIMIT = 4096
SEPARATOR_TAG = "<SEPARATE>"
MSG_NO_GOAL = "No current goal"
MSG_NO_HYP_MOVE = "No hyp to move"
MSG_NO_DEP_INFO = "No dependency info available"

# Coq script templates
SHOW_SCRIPT = f"""
idtac "{SEPARATOR_TAG}".
Show 1.
idtac "{SEPARATOR_TAG}".
Set Printing All.
Show 1.
Unset Printing All.
idtac "{SEPARATOR_TAG}".
_my_move_hyp.
Show 1.
idtac "{SEPARATOR_TAG}".
depinfo.
idtac "{SEPARATOR_TAG}".
Abort.
"""

# Script to use when there's no active proof
EMPTY_SHOW_SCRIPT = f"""
Goal True.
idtac "{SEPARATOR_TAG}".
idtac "{MSG_NO_GOAL}".
idtac "{SEPARATOR_TAG}".
idtac "{MSG_NO_GOAL}".
idtac "{SEPARATOR_TAG}".
idtac "{MSG_NO_HYP_MOVE} or no current goal".
idtac "{SEPARATOR_TAG}".
idtac "{MSG_NO_DEP_INFO}".
idtac "{SEPARATOR_TAG}".
Abort.
"""


# =============================================================================
# Data Classes
# =============================================================================

class GoalState:
    """
    Represents the state of a proof goal with various representations.
    
    Attributes:
        init: Initial goal representation
        moved: Goal representation after moving hypotheses
        raw: Raw goal representation with all printing options
        all: String representation of all goals
        defs: List of (name, definition) tuples for referenced constants
    """
    
    def __init__(
        self, 
        init: str, 
        moved: str, 
        raw: str, 
        all: str,
        defs: list[tuple[str, str]]
    ):
        self.init = init
        self.moved = moved
        self.raw = raw
        self.all = all
        self.defs = defs
    
    def __repr__(self):
        init_preview = self.init[:50] if len(self.init) > 50 else self.init
        moved_preview = self.moved[:50] if len(self.moved) > 50 else self.moved
        raw_preview = self.raw[:50] if len(self.raw) > 50 else self.raw
        all_preview = self.all[:50] if len(self.all) > 50 else self.all
        return (f"GoalState(init={init_preview}..., moved={moved_preview}..., "
                f"raw={raw_preview}..., all={all_preview}..., defs={len(self.defs)} items)")


# =============================================================================
# Utility Functions
# =============================================================================

def truncate_def(text: str, max_limit: int = DEF_MAX_LIMIT) -> str:
    """
    Truncate definition text if it exceeds the maximum limit.
    
    Args:
        text: The definition text to truncate
        max_limit: Maximum allowed length (default: DEF_MAX_LIMIT)
    
    Returns:
        Truncated text with '...' appended if needed
    """
    if len(text) > max_limit:
        return text[:max_limit] + '...'
    return text


def compile_coq_file(
    file_path: str, 
    project_dir: str, 
    content: str, 
    compile_args: list[str]
) -> tuple[str, str]:
    """
    Compile a Coq file and return its output.
    
    Args:
        file_path: Path to the Coq file
        project_dir: Project directory for compilation context
        content: Content to write to the file
        compile_args: Additional compilation arguments
    
    Returns:
        Tuple of (stdout, stderr) from the compilation
    
    Raises:
        AssertionError: If compilation process fails to start
    """
    with open(file_path, 'w') as f:
        f.write(content)
    
    try:
        result = subprocess.run(
            ['coqc', file_path] + compile_args,
            text=True,
            capture_output=True,
            cwd=project_dir
        )
        return result.stdout, result.stderr
    except Exception as e:
        assert False, f"Error when running: coqc {file_path} {compile_args}: {e}"


def parse_goal(output: str) -> str:
    """
    Parse goal output from Coq and extract the actual goal text.
    
    Args:
        output: Raw output from Coq's Show command
    
    Returns:
        Parsed goal text or "No current goal" if none exists
    """
    # Check for no goal messages
    if MSG_NO_GOAL in output or MSG_NO_HYP_MOVE in output:
        return MSG_NO_GOAL

    # Look for 'is:' marker that precedes the goal
    is_marker = 'is:'
    is_pos = output.find(is_marker)
    
    if is_pos == -1:
        # No 'is:' marker found - might be no goal or different format
        stripped_output = output.strip()
        logger.warning(f"No 'is:' marker found in output: {output}")
        return stripped_output if stripped_output else MSG_NO_GOAL
    
    # Extract and clean the goal text after 'is:'
    goal_text = output[is_pos + len(is_marker):]
    output_lines = goal_text.split('\n')
    cleaned_lines = [line.strip() for line in output_lines if line.strip()]
    result = '\n'.join(cleaned_lines)
    
    return result if result else MSG_NO_GOAL


def extract_num_goals(show_output: str) -> int:
    """
    Extract the number of goals from 'Show.' output.
    
    Args:
        show_output: Raw output from Coq's 'Show.' command
    
    Returns:
        Number of goals (0 if no goals or error parsing)
    
    Example formats:
        "1 subgoal" -> 1
        "3 subgoals" -> 3
        "3 focused goals (2 shelved) -> 3"
        "This subgoal is:" -> 1
        "No current goal" -> 0
    """
    logger.info("Extracting number of goals from: " + show_output)
    if not show_output or MSG_NO_GOAL in show_output:
        return 0
    
    # Look for "N subgoal(s)" or "N goal(s)" pattern (handles "focused" modifier)
    match = re.search(r'(\d+)\s+(?:\w+\s+)?(?:sub)?goals?', show_output)
    if match:
        return int(match.group(1))
    
    # If we see "This subgoal is:" or similar, it's a single goal
    if 'subgoal is:' in show_output.lower() or '====' in show_output:
        return 1
    
    return 0


def parse_all_goals(show_outputs: list[str]) -> str:
    """
    Parse and format all goals in a consistent format (like Show 1).
    
    This function takes outputs from Show commands for multiple goals
    and formats them consistently. Each goal is presented with its full
    context (hypotheses and conclusion) in the same format as 'Show 1.'.
    
    Args:
        show_outputs: List of raw outputs from Coq's Show commands.
                     Each element should be output from Show N for goal N.
                     Empty strings indicate no more goals.
    
    Returns:
        Formatted string containing all goals, or "No current goal" if none exist.
        
    Example format for multiple goals:
        Goal 1:
        <hypotheses>
        ============================
        <conclusion>
        
        Goal 2:
        <hypotheses>
        ============================
        <conclusion>
    """
    if not show_outputs:
        return MSG_NO_GOAL
    
    formatted_goals = []
    
    for idx, output in enumerate(show_outputs, start=1):
        if not output or not output.strip():
            break
            
        parsed = parse_goal(output)
        
        if parsed == MSG_NO_GOAL:
            break
        
        # Format each goal with a header if multiple goals exist
        if len([o for o in show_outputs if o and o.strip()]) > 1:
            formatted_goals.append(f"Subgoal {idx}:\n{parsed}")
        else:
            # Single goal - no need for header
            formatted_goals.append(parsed)
    
    if not formatted_goals:
        return MSG_NO_GOAL
    
    return "\n\n".join(formatted_goals)


def get_all_goals(
    script: str,
    file_path: str,
    project_dir: str,
    compile_args: list[str]
) -> str:
    """
    Get all goals in the current proof state, formatted consistently.
    
    This function first uses 'Show.' to determine the number of goals,
    then uses 'Show N.' for each goal to get their full context.
    
    Args:
        script: Current Coq script content
        file_path: Path to the Coq file
        project_dir: Project directory
        compile_args: Compilation arguments
    
    Returns:
        Formatted string containing all goals in Show 1 format
    """
    # First, get the number of goals using Show.
    show_count_script = f"""
idtac "{SEPARATOR_TAG}".
Show.
idtac "{SEPARATOR_TAG}".
Abort.
"""
    
    stdout, _ = compile_coq_file(
        file_path, project_dir,
        script + show_count_script,
        compile_args
    )
    
    segments = stdout.split(SEPARATOR_TAG)
    if len(segments) < 2:
        return MSG_NO_GOAL
    
    show_output = segments[1]
    num_goals = extract_num_goals(show_output)
    
    if num_goals == 0:
        return MSG_NO_GOAL
    
    # Now get all individual goals
    separator = f'\nidtac "{SEPARATOR_TAG}".\n'
    show_commands = [f'Show {i}.' for i in range(1, num_goals + 1)]
    all_goals_script = separator + separator.join(show_commands) + separator + 'Abort.\n'
    
    _, all_goals_stdout, _ = remove_failing_commands(
        script,
        all_goals_script,
        file_path,
        project_dir,
        compile_args
    )
    
    # Parse individual goal outputs
    goal_segments = all_goals_stdout.split(SEPARATOR_TAG)
    goal_outputs = [
        goal_segments[i].strip() 
        for i in range(1, len(goal_segments)) 
        if i <= num_goals and goal_segments[i].strip()
    ]
    
    return parse_all_goals(goal_outputs)


def parse_depinfo_tactics(output: str) -> str:
    """
    Parse dependency information tactics from Coq output.
    
    Args:
        output: Raw output containing dependency information
    
    Returns:
        Cleaned tactics string (excluding first and last lines)
    """
    lines = output.split('\n')
    # Skip first and last lines, keep only non-empty lines
    relevant_lines = [line.strip() for line in lines[1:-1] if line.strip()]
    return '\n'.join(relevant_lines)

def extract_blocks(blkname: str, text: str) -> list[str]:
    """
    Extract all substrings wrapped by XML-style tags.
    
    Args:
        blkname: Name of the tag (e.g., 'print', 'check')
        text: Text containing tagged blocks
    
    Returns:
        List of extracted inner texts (without the tags)
    
    Example:
        extract_blocks('name', '<name>foo</name>') returns ['foo']
    """
    pattern = re.compile(
        rf"<{re.escape(blkname)}>(.*?)</{re.escape(blkname)}>",
        re.DOTALL
    )
    return [match.strip() for match in pattern.findall(text)]


def parse_name_arguments(name_raw: dict) -> list[str]:
    """
    Parse name arguments from various input formats.
    
    Args:
        name_raw: Dictionary containing 'names' key with string or list value
    
    Returns:
        List of cleaned name strings
    """
    name_data = name_raw.get('names', [])
    
    if isinstance(name_data, str):
        # Handle string format: "[name1, name2]" or "name1, name2"
        name_data = name_data.strip('[]')
        names = [x.strip() for x in name_data.split(',') if x.strip()]
    elif isinstance(name_data, list):
        # Handle list format: clean each element
        names = [
            str(x).strip().strip('"').strip("'") 
            for x in name_data 
            if str(x).strip()
        ]
    else:
        names = []
    
    return names


def remove_failing_commands(
    header: str, 
    script: str, 
    file_path: str, 
    project_dir: str, 
    compile_args: list[str]
) -> tuple[str, str, list[tuple[str, str]]]:
    """
    Iteratively remove commands that cause compilation errors.
    
    This function attempts to compile a script and removes failing commands
    one by one until the script compiles successfully or no errors remain.
    
    Args:
        header: Fixed header content that won't be removed
        script: Script content that may contain failing commands
        file_path: Path to the Coq file
        project_dir: Project directory for compilation
        compile_args: Additional compilation arguments
    
    Returns:
        Tuple of (cleaned_script, stdout, list_of_failed_commands)
        where failed_commands is list of (command_name, error_message) tuples
    """
    # Normalize header
    header = '\n'.join([
        line.strip() 
        for line in header.split('\n') 
        if line.strip()
    ]) + '\n'
    header_length = len(header)
    
    full_script = header + script
    failed_commands: list[tuple[str, str]] = []
    
    while True:
        stdout, stderr = compile_coq_file(
            file_path, project_dir, full_script, compile_args
        )
        stderr = stderr.strip()
        
        error_pos = stderr.find('Error:')
        
        # Check if compilation succeeded or only has "needs to be closed" error
        if error_pos == -1 or stderr.endswith((
            'needs to be closed.',
            'need to be closed.'
        )):
            assert full_script.startswith(header)
            return full_script[header_length:], stdout, failed_commands
        
        # Extract error information
        line_marker = 'line '
        line_pos = stderr.rfind(line_marker)
        if line_pos == -1:
            # Can't parse line number, return what we have
            return full_script[header_length:], stdout, failed_commands
        
        # Parse line number
        line_info = stderr[line_pos + len(line_marker):]
        comma_pos = line_info.find(',')
        if comma_pos == -1:
            return full_script[header_length:], stdout, failed_commands
        
        line_number = int(line_info[:comma_pos]) - 1
        error_content = stderr[error_pos:]
        
        # Remove the failing line
        script_lines = full_script.split('\n')
        if line_number < len(script_lines):
            failing_line = script_lines[line_number].strip()
            if failing_line.endswith('.'):
                failing_line = failing_line[:-1]
            command_name = failing_line.split()[-1] if failing_line else 'unknown'
            failed_commands.append((command_name, error_content))
            
            script_lines = script_lines[:line_number] + script_lines[line_number + 1:]
            full_script = '\n'.join([line for line in script_lines if line.strip()])


# =============================================================================
# Definition Retrieval
# =============================================================================

def print_definitions(
    lctx: LocalContext, 
    name_args: dict, 
    current_script: str, 
    save_name: str | None = None
) -> list[tuple[str, str]]:
    """
    Retrieve and print definitions for specified Coq constants.
    
    Args:
        lctx: Local context containing proof environment
        name_args: Dictionary with 'names' key containing constant names
        current_script: Current Coq script content
        save_name: Optional filename to save results
    
    Returns:
        List of (name, definition) tuples for successfully retrieved definitions
    """
    original_text = current_script
    names = parse_name_arguments(name_args)

    # Get compilation context
    env_dup = lctx.penv_dup
    file_path = env_dup.fpath
    project_dir = env_dup.workspace or prover_root
    compile_args = lctx.compile_instr
    
    # Build print script
    separator = f'\nidtac "{SEPARATOR_TAG}".\n'
    print_commands = [
        f'Print {name}.{separator}Print "{name}".' 
        for name in names
    ]
    print_script = separator + separator.join(print_commands) + separator + 'Abort.\n'

    # Attempt to compile and remove failing commands
    cleaned_script, stdout, failed_commands = remove_failing_commands(
        current_script.strip(),
        print_script,
        file_path,
        project_dir, 
        compile_args
    )

    # Parse successful commands
    successful_commands = cleaned_script.split(separator.strip())
    output_segments = stdout.split(SEPARATOR_TAG)
    
    results = []
    processed_names = set()
    
    for i, command in enumerate(successful_commands):
        command = command.strip()
        if not command.startswith('Print'):
            continue
        
        # Extract name from command
        name = command[:-1].split()[-1].strip().strip('"')
        if name in processed_names:
            continue
        
        processed_names.add(name)
        if i < len(output_segments):
            output_content = truncate_def(output_segments[i].strip())
            results.append((name, output_content))

    # Add error information for failed commands
    for command_name, error_info in failed_commands:
        name = command_name.strip().strip('"')
        if name in processed_names:
            continue
        results.append((name, f'Error when Printing: {error_info.strip()}'))

    # Restore original file
    compile_coq_file(file_path, project_dir, original_text, compile_args)

    # Optionally save results
    if save_name is not None:
        save_location = os.path.join(get_output_dir(), 'prompts', save_name)
        with open(save_location, 'w') as f:
            f.write(str(results))

    return results
    

# =============================================================================
# State Parsing
# =============================================================================

def _check_has_active_proof(
    file_path: str, 
    project_dir: str, 
    script: str, 
    compile_args: list[str]
) -> bool:
    """
    Check if the current script has an active proof.
    
    Args:
        file_path: Path to the Coq file
        project_dir: Project directory
        script: Current script content
        compile_args: Compilation arguments
    
    Returns:
        True if there's an active proof, False otherwise
    """
    _, stderr = compile_coq_file(
        file_path, project_dir, 
        script + '\nShow.\n', 
        compile_args
    )
    return 'This command requires an open proof' not in stderr


def _parse_goal_safely(output_segment: str, goal_type: str) -> str:
    """
    Safely parse a goal from output segment with error handling.
    
    Args:
        output_segment: Output segment to parse
        goal_type: Type of goal being parsed (for logging)
    
    Returns:
        Parsed goal text or "No current goal" if parsing fails
    """
    try:
        if len(output_segment.strip()) > 0:
            return parse_goal(output_segment)
        else:
            return MSG_NO_GOAL
    except Exception as e:
        logger.warning(f"Failed to parse {goal_type} goal: {e}")
        return MSG_NO_GOAL


def _extract_dependency_tactics(output_segment: str) -> str:
    """
    Extract and clean dependency tactics from output.
    
    Args:
        output_segment: Output segment containing dependency info
    
    Returns:
        Cleaned dependency tactics script ending with 'Abort.'
    """
    try:
        if (output_segment.strip() and 
            output_segment.strip() != MSG_NO_DEP_INFO):
            tactics = parse_depinfo_tactics(output_segment.strip()) + '\nAbort.\n'
            # Clean up tactics
            tactics = tactics.replace('@', '').replace('Print Term', 'Print Term Term')
            return tactics
        else:
            return 'Abort.\n'
    except Exception as e:
        logger.warning(f"Failed to parse depinfo: {e}")
        return 'Abort.\n'


def _extract_definitions_from_output(output: str) -> list[tuple[str, str]]:
    """
    Extract definitions from compilation output.
    
    Args:
        output: Compilation output containing print/check blocks
    
    Returns:
        Sorted list of (name, definition) tuples
    """
    print_blocks = extract_blocks('print', output)
    check_blocks = extract_blocks('check', output)

    defs_map = {}
    for block in print_blocks + check_blocks:
        name_blocks = extract_blocks('name', block)
        if not name_blocks:
            continue
        
        name = name_blocks[0]
        name_end_pos = block.find('</name>') + 7
        def_text = block[name_end_pos:].strip()
        
        if name not in defs_map:
            defs_map[name] = truncate_def(def_text)

    # Return sorted list of definitions
    return sorted([
        (name, defn) 
        for name, defn in defs_map.items() 
        if defn is not None
    ])


def parse_state(
    lctx: LocalContext, 
    script: str, 
    print_all: bool = False
) -> GoalState:
    """
    Parse the current proof state from a Coq script.
    
    This function compiles the script with special commands to extract:
    - Initial goal representation
    - Goal after moving hypotheses
    - Raw goal with full printing
    - Definitions of referenced constants
    
    Args:
        lctx: Local context containing proof environment
        script: Current Coq script content
    
    Returns:
        GoalState containing all extracted information
    """
    original_script = script
    
    # Get compilation context
    env_dup = lctx.penv_dup
    file_path = env_dup.fpath
    project_dir = env_dup.workspace or prover_root
    compile_args = lctx.compile_instr
    script = script + '\n'
    
    # Check if there's an active proof and use appropriate script
    has_active_proof = _check_has_active_proof(
        file_path, project_dir, script, compile_args
    )
    
    logger.info(f"Has active proof: {has_active_proof}")
    
    if has_active_proof:
        stdout, _ = compile_coq_file(
            file_path, project_dir, 
            script + SHOW_SCRIPT, 
            compile_args
        )
        logger.info("SHOW_SCRIPT executed.")
        logger.info(f"SHOW_SCRIPT: {SHOW_SCRIPT}")
        logger.info(f"SHOW_SCRIPT output: {stdout}")
    else:
        stdout, _ = compile_coq_file(
            file_path, project_dir, 
            script + EMPTY_SHOW_SCRIPT, 
            compile_args
        )
        logger.info("EMPTY_SHOW_SCRIPT executed.")
    
    # Split output into segments
    output_segments = stdout.split(SEPARATOR_TAG)
    
    # Ensure we have enough segments (now 5 after removing Show.)
    if len(output_segments) < 5:
        logger.warning(
            f"SHOW_SCRIPT returned insufficient segments: "
            f"{len(output_segments)} instead of 5"
        )
        while len(output_segments) < 5:
            output_segments.append("")
    
    # Parse goals safely (order: init -> raw -> moved)
    goal_init = _parse_goal_safely(output_segments[1], "init")
    goal_raw = _parse_goal_safely(output_segments[2], "raw")
    goal_moved = _parse_goal_safely(output_segments[3], "moved")
    
    # Extract dependency tactics
    dep_tactics = _extract_dependency_tactics(
        output_segments[4] if len(output_segments) > 4 else ""
    )

    if print_all:
        goal_all = get_all_goals(script, file_path, project_dir, compile_args)
    else:
        goal_all = ""

    # Process dependency information if available
    if dep_tactics.strip() != 'Abort.':
        _, stdout, _ = remove_failing_commands(
            script, 
            dep_tactics,                              
            file_path, 
            project_dir, 
            compile_args
        )
    else:
        # No dependency info to process
        stdout, _ = compile_coq_file(
            file_path, project_dir, script, compile_args
        )

    # Extract definitions from output
    definitions = _extract_definitions_from_output(stdout)

    compile_coq_file(file_path, project_dir, original_script, compile_args)
    
    return GoalState(
        init=goal_init,
        moved=goal_moved,
        raw=goal_raw,
        all=goal_all,
        defs=definitions
    )



# =============================================================================
# Legacy State Parsing (using ProofFile API)
# =============================================================================

"""
def parse_state_old(
    lctx: LocalContext, 
    pfile: ProofFile, 
    logger: Logger, 
    ctx_terms: dict[str, Term]
) -> GoalState:
    Legacy method to parse state using ProofFile API.
    
    Args:
        lctx: Local context
        pfile: ProofFile instance
        logger: Logger instance
        ctx_terms: Dictionary of context terms
    
    Returns:
        GoalState with parsed information
    goal_text: dict[str, str] = {}
    current_step = lctx.nstep()
    
    # Get initial goal
    raw_goal = pfile.current_goals.goals.goals[0]
    goal_text['init'] = pretty_goals([raw_goal])
    
    # Get goal after moving hypotheses
    pfile.add_step(current_step, ' _my_move_hyp. ')
    pfile.exec(1)
    goal_text['moved'] = pretty_goals([pfile.current_goals.goals.goals[0]])
    pfile.delete_step(current_step + 1)

    # Get raw goal with full printing
    pfile.add_step(current_step, ' Set Printing All. ')
    raw_goal = pfile.current_goals.goals.goals[0]
    goal_text['raw'] = pretty_goals([raw_goal])
    logger.info(f'Goal Text Loaded:\n{goal_text["raw"]}')

    # Extract names from goal and hypotheses
    raw_hyps = pfile.current_goals.goals.goals[0].hyps
    name_set = set()
    
    # Extract names from goal type
    try:
        pfile.add_step(current_step + 1, f' Check ({raw_goal.ty}). ')
        name_set = name_set.union(
            set(get_names(pfile.steps[-1].ast.span['v']['expr']))
        )
        pfile.delete_step(current_step + 2)
    except Exception:
        logger.warning(f'Error when parsing {raw_goal.ty}')

    # Extract names from hypotheses
    for hyp in raw_hyps:
        try:
            pfile.add_step(current_step + 1, f' Check ({hyp.ty}). ')
            name_set = name_set.union(
                set(get_names(pfile.steps[-1].ast.span['v']['expr']))
            )
            pfile.delete_step(current_step + 2)
        except Exception:
            logger.warning(f'Error when parsing {hyp.ty}')
    
    pfile.delete_step(current_step + 1)

    # Retrieve definitions for all names
    definitions = []
    for name in sorted(name_set):
        text = None
        assert pfile.is_valid
        
        try:
            pfile.add_step(current_step, f' Print {name}. ')
            text = str(pfile.steps[-1].message)
            pfile.delete_step(current_step + 1)
        except Exception:
            logger.warning(f'Error when printing {name}')
            if name in ctx_terms:
                text = ctx_terms[name].text
            else:
                logger.warning(f'ctx also not found {name}')
        
        if text is None:
            continue
        
        # Truncate if too long
        if len(text) > DEF_MAX_LIMIT:
            text = text[:DEF_MAX_LIMIT] + '...'
        
        # Skip parsing-only and Ltac definitions
        if '(only parsing)' in text or 'Ltac' in text:
            continue
        
        definitions.append((name, text))

    return GoalState(
        init=goal_text['init'],
        moved=goal_text['moved'],
        raw=goal_text['raw'],
        defs=definitions
    )
"""

# =============================================================================
# Tool Definitions
# =============================================================================

DEF_TOOL = {
    "name": "get_definition",
    "description": "get the definition of a Coq constant",
    "parameters": {
        "type": "object",
        "properties": {
            "names": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "A list of qualified identifiers of Coq constants to get definitions for. e.g., ['List.map', 'canonical']"
            },
        },
        "required": ["names"]
    }
}


# =============================================================================
# Error Message Augmentation
# =============================================================================

def _create_search_script(name: str) -> str:
    """
    Create a Coq script to search for a name.
    
    Args:
        name: Name to search for (qualified names will be shortened)
    
    Returns:
        Coq script that searches for the name
    """
    # For qualified names, use only the last component
    if '.' in name:
        name = name[name.rfind('.') + 1:]
    
    return f'''
idtac "<search>".
Search "{name}".
idtac "</search>".
'''


def _format_notfound_message(name: str, search_result: str) -> str:
    """
    Format a "not found" error message with optional alternatives.
    
    Args:
        name: Name that was not found
        search_result: Search results with alternatives (may be empty)
    
    Returns:
        Formatted error message
    """
    if not search_result:
        return f"""
The reference {name} was NOT found in the current enviornment.
"""
    return f"""
The reference {name} was NOT found in the current enviornment. 
Consider avaliable alternatives:
{search_result}
"""


def augment_notfound_message(
    error_msg: str, 
    verified_script: str, 
    file_path: str,
    project_dir: str,
    compile_args: list[str],
    msg_limit: int = 640
) -> str:
    """
    Augment "not found" error messages with search results.
    
    Extracts the name from the error message, searches for similar names,
    and returns an enhanced error message with alternatives.
    
    Args:
        error_msg: Original error message
        verified_script: Currently verified Coq script
        file_path: Path to Coq file
        project_dir: Project directory
        compile_args: Compilation arguments
        msg_limit: Maximum length of returned message
    
    Returns:
        Enhanced error message with alternatives (truncated to msg_limit)
    """
    # Extract name from error message
    not_found_marker = 'was not found in the current'
    marker_pos = error_msg.find(not_found_marker)
    if marker_pos == -1:
        return error_msg
    
    name = error_msg[:marker_pos].strip().split()[-1].strip()

    # Skip very short names (likely false positives)
    if len(name) <= 3:
        return error_msg

    # Search for alternatives
    stdout, stderr = compile_coq_file(
        file_path, project_dir,
        verified_script + _create_search_script(name),
        compile_args
    )
    
    # Extract search results
    search_blocks = extract_blocks('search', stdout)
    search_result = search_blocks[0].strip() if search_blocks else ""
    
    # Format and truncate message
    enhanced_msg = _format_notfound_message(name, search_result)
    return enhanced_msg[:msg_limit]


'''
def augment_environment_prefix(error_msg: str) -> str:
    """
    Remove "In environment" prefix and context from error messages.
    
    Strips out the environment listing at the start of error messages
    to make them more concise.
    
    Args:
        error_msg: Error message to clean
    
    Returns:
        Error message with environment prefix removed
    """
    lines = error_msg.split('\n')
    
    for i, line in enumerate(lines):
        # Skip "In environment" lines and variable declarations
        if line.strip().startswith('In environment'):
            continue
        if ' : ' in line or ' := ' in line or line.startswith(' '):
            continue
        
        # Found the first line that's not part of the environment listing
        return '\n'.join(lines[i:])
    
    return error_msg
'''
