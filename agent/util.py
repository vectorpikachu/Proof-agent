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

# 从 “characters X” 或 “characters X-Y” 中同时捕获开始/结束位置
errfmt = re.compile(r'line\s+(\d+),\s*characters\s+(\d+)(?:-(\d+))?')

def truncate_on_error(err: str, text: str) -> str:
    """
    根据 err 中的行列信息截断 text，并返回截断后的内容。
    这次截断会包含整个触发报错的字符范围（X–Y）。
    """

    m = None
    for last_match in errfmt.finditer(err):
        m = last_match

    if not m:
        return text

    line_no = int(m.group(1)) - 1    # 0-based
    end_pos = int(m.group(3) or m.group(2))  # 如果有结束位置就用，没有就当单字符

    #print(line_no, end_pos)

    lines = text.split('\n')
    if 0 <= line_no < len(lines):
        # 用 end_pos 截断，确保包含了触发错误的全部字符
        truncated_line = lines[line_no][:end_pos]
        lines = lines[:line_no] + [truncated_line]

    return '\n'.join(lines)

