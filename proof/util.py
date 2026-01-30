from typing import List, Optional
from coqpyt.coq.lsp.structs import Goal, GoalConfig, GoalAnswer
from coqpyt.coq.structs import Step, TermType
from coqpyt.coq.context import FileContext
import sys, re

pattern = re.compile(r'```coq\n(.*?)\n```', re.DOTALL)
def getscript(response: str) -> str:
    try:
        response = response[response.rfind('```coq'):]
        ans: str = pattern.findall(response)[-1]
        #print(ans)
        return (ans.replace('Admitted.', '')
                .replace('admit.', '')
                .replace('Abort.', '')
                .replace('Aborted.', '')
                .replace('  2: apply unique_key_compute_code; auto.', 'apply unique_key_compute_code; auto.'))
    except:
        return ''


def omit_before(x: str, line: int):
    return '\n'.join(x.split('\n')[line:])

def __exists(f, l):
    for x in l:
        if f(x): return True
    return False

def pretty_goals(goals: List[Goal]) -> str:
    bold = lambda text: "** " + text + " **" 
    if len(goals) > 0:
        res = repr(goals[0]) + '\n\n'
        for i, goal in enumerate(goals[1:]):
            res += bold(f'[Unfocused Goal {i + 1}]') + '\n\n'
            res += repr(goal) + "\n\n"
    else:
        res = "No more goals."
    return res.replace('∀', 'forall').replace('∃', 'exists')

def invalid(step: Step):
    return __exists(lambda x: x.severity <= 1, step.diagnostics)

def get_err_msg(step: Step):
    if not invalid(step):
        return True, ''
    return False, '\n'.join(list(map(lambda x: x.message, step.diagnostics)))

def get_goal_cfg(current_goals: GoalAnswer) -> Optional[GoalConfig]:
    cur_goals = current_goals
    if cur_goals is not None:
        return cur_goals.goals
    return None

def is_end_proof(ctx: FileContext, step: Step):
    return ctx.expr(step)[0] in ["VernacEndProof", "VernacExactProof"]
def is_end_subproof(ctx: FileContext, step: Step):
    return ctx.expr(step)[0] in ["VernacEndSubproof"]

def no_goal(goal_cfg: Optional[GoalConfig]) -> bool:
    if goal_cfg is None:
        return True
    return (goal_cfg.goals == []) and (goal_cfg.given_up == [])

def is_bullet(ctx: FileContext, step: Step):
    return ctx.expr(step)[0] == "VernacBullet"

def switch_next_goal(ctx: FileContext, steps: List[Step], 
                     step_index: int):

    bullet_stack = set()
    for (i, step) in enumerate(steps[:step_index]):
        if is_bullet(ctx, step):
            bullet_stack.add(step.text.lstrip().rstrip())
    
    #print('rest proof =', steps[step_index:])
    for (i, step) in enumerate(steps[step_index:]):
        if ctx.term_type(step) != TermType.OTHER:
            return steps[i + step_index:]
        if is_end_proof(ctx, step):
            return steps[i + step_index:]
        if is_bullet(ctx, step) and step.text.lstrip().rstrip() in bullet_stack:
            return steps[i + step_index:]
    
    return []

def map_text(steps: List[Step]):
    return list(map(lambda x: x.text, steps))

