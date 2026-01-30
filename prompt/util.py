from enum import Enum
from typing import Tuple, List, Dict
import hashlib, logging

logger = logging.getLogger('Prompt-Util')

class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

class ModelHub(Enum):
    GPTO3 = {
        'name': 'yunwu/hq-o3-2025-04-16',
        'need_budget': False,
        'max_tokens': 100000,
        'azure': False
    }

    AzureO4Mini = {
        'name': 'o4-mini',
        'need_budget': False,
        'max_tokens': 100000,
        'azure': True
    }

    GPTO4Mini = {
        'name': 'yunwu/hq-o4-mini-2025-04-16',
        'need_budget': False,
        'max_tokens': 100000,
    }

    GPTO4MiniHigh = {
        'name': 'yunwu/hq-o4-mini-2025-04-16',
        'need_budget': False,
        'max_tokens': 100000,
        "reasoning_effort": "high"
    }


    GPT5 = {
        'name': 'yunwu/gpt-5-2025-08-07',
        'need_budget': False,
        'max_tokens': 8192,
    }

    YunwuGPTO4Mini = {
        'name': 'o4-mini-2025-04-16',
        'need_budget': False,
        'max_tokens': 100000,
        'yunwu': True
    }

    YunwuGPT4 = {
        # 'name': 'gpt-4-32K-0613',
        'name': 'gpt-4',
        # 'name' : 'gpt-4-1106-preview',
        'need_budget': False,
        'max_tokens': 100000,
        'yunwu': True
    }
    YunwuGPT4_1106 = {
    #    'name': 'gpt-4-1106-preview',
        'name': 'yunwu/hq-gpt-4-turbo-2024-04-09',
        'need_budget': False,
        'max_tokens': 100000
        # 'yunwu': True
    }
    QingyunGPT4 = {
        'name': 'gpt-4-32k',
        'need_budget': False,
        'max_tokens': 100000,
        'qingyun': True
    }


    GPTO3Mini = {
        'name': "yunwu/o3-mini-2025-01-31", 
        'need_budget': False,
        'max_tokens': 100000
    }

    GPT4o = {
        'name': 'yunwu/gpt-4o', 
        'need_budget': False, 
        'max_tokens': 128000
    }

    Claude37 = {
        'name': 'aws/claude-3-7-sonnet-20250219', 
        'need_budget': True,
        'max_tokens': 128000
    }

    QwenMax = {
        'name': 'ali/qwen-max-latest', 
        'need_budget': False,
        'max_tokens': 8192
    }

    Qwen3Plus = {
        "name": "ali/qwen3-235b-a22b-thinking",
        "max_tokens": 32000
    }

    def need_budget(self):
        return self.value.get('need_budget', False)

    def name(self):
        return self.value['name']
    def is_azure(self):
        return self.value.get('azure', False)
    def is_yunwu(self):
        return self.value.get('yunwu', False)
    def is_qingyun(self):
        return self.value.get('qingyun', False)

    def has_effort(self):
        return 'reasoning_effort' in self.value

    def get_effort(self):
        if not self.has_effort():
            assert False, f'Model {self.name()} does not have reasoning effort'
        return self.value['reasoning_effort']

    def get_platform(self):
        if self.is_azure():
            return 'azure'
        elif self.is_yunwu():
            return 'yunwu'
        elif self.is_qingyun():
            return 'qingyun'
        else:
            return 'litellm'
    

def str_to_model(name: str):
    match name:
        case 'yunwu-gpt4':
            return ModelHub.YunwuGPT4
        case 'yunwu-gpt4-1106':
            return ModelHub.YunwuGPT4_1106
        case 'qingyun-gpt4':
            return ModelHub.QingyunGPT4
        case 'GPT4o':
            return ModelHub.GPT4o
        case 'Claude37':
            return ModelHub.Claude37
        case 'o3' | 'GPTO3':
            return ModelHub.GPTO3
        case 'o3mini' | 'GPTO3Mini':
            return ModelHub.GPTO3Mini
        case 'o4mini' | 'AzureO4Mini':
            return ModelHub.AzureO4Mini
        case 'GPTO4Mini':
            return ModelHub.GPTO4Mini
        case 'GPT5':
            return ModelHub.GPT5
        case 'YunwuGPTO4Mini':
            return ModelHub.YunwuGPTO4Mini
        case 'QwenMax':
            return ModelHub.QwenMax
        case 'Qwen3Plus':
            return ModelHub.Qwen3Plus
        case _:
            assert False

def to_model(val: str):
    if val.find('o3') != -1:
        return ModelHub.GPTO3Mini
    if val.find('4o') != -1:
        return ModelHub.GPT4o
    if val.find('claude') != -1:
        return ModelHub.Claude37
    if val.find('5') != -1:
        return ModelHub.GPT5
    assert False

def to_role(val: str):
    match val:
        case 'system':
            return Role.SYSTEM
        case 'user':
            return Role.USER
        case 'assistant':
            return Role.ASSISTANT
        case 'tool':
            return Role.TOOL
        case _:
            assert False

def to_dict(msg: Tuple[Role, str]):
    return {'role': str(msg[0].value), 'content': msg[1]}

class ChatHistory:
    def __init__(self, history: List[Dict]):
        self.history: List[Tuple[Role, str]] = []
        for msg in history:
            self.history.append((to_role(msg['role']), msg['content']))
    
    def _add_msg(self, role: Role, content: str):
        self.history.append((role, content))

    def add_msg(self, msg: Dict):
        self.history.append((to_role(msg['role']), msg['content']))
    
    def pop_msg(self):
        self.history.pop()

    def last_msg(self) -> Dict:
        if self.history == []:
            assert False
        return to_dict(self.history[-1])
    
    def dump(self) -> List[Dict]:
        ans = []
        for e in self.history:
            ans.append(to_dict(e))
        return ans

    def md5(self, mod: ModelHub):
        ans = str(mod.value)
        for e in self.history:
            #logger.log(15, f'Role = {e[0].value}')
            #logger.log(15, f'System = {hashlib.md5(e[1].encode()).hexdigest()}')
            ans += e[0].value + '\n<SEP>\n' + e[1] + '\n<SEP>\n'

        return hashlib.md5(ans.encode()).hexdigest()
    
if __name__ == '__main__':
    print(str(Role.SYSTEM.value))
    mod = ModelHub.Claude37
    print(mod)
    print(ModelHub.GPT4o.value)

