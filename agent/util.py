from coqpyt.coq.structs import GoalAnswer
from proof.util import pretty_goals, getscript
from typing import Dict, Optional
import re

_bullet_text = 'Focus next goal with bullet'
_btextlen = len(_bullet_text)

def nogoal(goal: GoalAnswer):
    return goal is None or goal.goals is None or (goal.goals.goals == [])

def goal_str(goal: GoalAnswer, only_focus: bool = True):
    if nogoal(goal):
        return ''
    if only_focus:
        return pretty_goals([goal.goals.goals[0]])
    return pretty_goals(goal.goals.goals)

def num_goals(goal: GoalAnswer):
    if nogoal(goal): return 0
    return len(goal.goals.goals)

# Capture start/end positions from "characters X" or "characters X-Y"
errfmt = re.compile(r'line\s+(\d+),\s*characters\s+(\d+)(?:-(\d+))?')

def truncate_on_error(err: str, text: str) -> str:
    """
    Truncate text based on line/column info from err.
    This truncation includes the entire character range (X-Y) that triggered the error.
    """

    m = None
    for last_match in errfmt.finditer(err):
        m = last_match

    if not m:
        return text

    line_no = int(m.group(1)) - 1    # 0-based
    end_pos = int(m.group(3) or m.group(2))  # Use end position if available, otherwise single char

    #print(line_no, end_pos)

    lines = text.split('\n')
    if 0 <= line_no < len(lines):
        # Truncate using end_pos to ensure all error-triggering characters are included
        truncated_line = lines[line_no][:end_pos]
        lines = lines[:line_no] + [truncated_line]

    return '\n'.join(lines)

