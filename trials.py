from logging import getLogger
from prompt.gen import ContextItem
from hashlib import md5
logger = getLogger('Trial')

class TrialItem:
    def __init__(self, pfstat: str, tactics: str, err_msg: str):
        self.pstate = pfstat
        self.tactics = tactics.lstrip().rstrip()
        self.err_msg = err_msg
        self.md5 = md5((tactics + '\n' + err_msg).encode()).hexdigest()

    def print(self, id):
        ans = f'### Trial {id}:\n\n'
        ans +=  '- Tactics Applied\n\n```coq\n'
        ans += self.tactics
        ans += '\n```\n\n- Error Message Reported by Coq-LSP\n\n'
        ans += self.err_msg
        return ans

        

trial_db: dict[str, tuple[list[TrialItem], set[str]]] = {}

def add_item(item: TrialItem):
    if item.pstate not in trial_db:
        trial_db[item.pstate] = (list(), set())
#    if item.md5 in trial_db[item.pstate][1]:
#        return
    trial_db[item.pstate][0].append(item)
    trial_db[item.pstate][1].add(item.md5)
 
def get_trials(goal: str):
    if goal not in trial_db:
        return list()
    lst = trial_db[goal][0]
    return '\n\n'.join([
        w.print(i) for i, w in enumerate(lst)
    ])

def num_explore(goal: str):
    if goal not in trial_db:
        return 0
    return len(trial_db[goal][0])

def merge_items(frm: str, to: str, head: str):
    if frm not in trial_db:
        return
    if to not in trial_db:
        trial_db[to] = (list(), set())
    for w in trial_db[frm][0]:
        item = TrialItem(
            to,
            head + '\n' + w.tactics,
            w.err_msg
        )
        add_item(item)
