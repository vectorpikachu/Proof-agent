import sys, pickle, os, logging, json, traceback
# Optional tokenizer for prompt truncation
try:
    import tiktoken  # type: ignore
except ImportError:  # pragma: no cover - soft dependency
    tiktoken = None
#logger.getLogger('openai').setLevel()
from env import api_key, base_url, verbose, get_output_dir
from env import get_prompt_cache_root
from env import aoai_api_key, aoai_base_url
from env import yunwu_api_key, yunwu_base_url
from env import qingyun_api_key, qingyun_base_url
import openai
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from prompt.util import ChatHistory, ModelHub
from openai import APITimeoutError, APIError, RateLimitError, APIConnectionError
from typing import Dict, Optional, List
import time, hashlib
from dataclasses import dataclass
from icecream import ic

client_yunwu = openai.OpenAI(
    api_key=yunwu_api_key,
    base_url=yunwu_base_url,
)
client_qingyun = openai.OpenAI(
    api_key=qingyun_api_key,
    base_url=qingyun_base_url,
)
client_azure = openai.AzureOpenAI(
    azure_endpoint=aoai_base_url,
    api_key=aoai_api_key,
    api_version='2024-12-01-preview'
)
client = openai.OpenAI(api_key=api_key, base_url=base_url)
logger = logging.getLogger('Prompt-Low-Level')
def chat_low_level(**kwargs):
    f = None
    platform = kwargs.get('platform')
    del kwargs['platform']
    match platform:
        case 'yunwu':
            kwargs['max_completion_tokens'] = kwargs['max_tokens']
            del kwargs['max_tokens']
            logger.info(f'LLM Call with kwargs: {kwargs}')
            f = lambda: client_yunwu.chat.completions.create(
                **kwargs
            )
        case 'qingyun':
            kwargs['max_completion_tokens'] = kwargs['max_tokens']
            del kwargs['max_tokens']
            logger.info(f'LLM Call with kwargs: {kwargs}')
            f = lambda: client_qingyun.chat.completions.create(
                **kwargs
            )
        case 'azure':
            kwargs['max_completion_tokens'] = kwargs['max_tokens']
            del kwargs['max_tokens']
            f = lambda: client_azure.chat.completions.create(
                **kwargs
            )            
        case _:
            kwargs['max_completion_tokens'] = kwargs['max_tokens']
            del kwargs['max_tokens']
            #kwargs['timeout'] = 1200
            logger.info(f'LLM Call with kwargs: {kwargs}')
            f = lambda: client.chat.completions.create(
                **kwargs
            )
            logger.info(f'LLM Call Prepared')

    retries = 0
    max_retries = 5
    while retries < max_retries:
        try:
            logger.info(f'LLM API Call, Attempt {retries + 1}/{max_retries}')
            result = f()
            logger.info(f'LLM API Call Succeeded')
            return result
        except (
            APITimeoutError,
            APIError,
            RateLimitError,
            APIConnectionError
        ) as e:
            retries += 1
            wait_time = 2 ** retries
            logger.info(f"Debugging: Exception occurred: {e}")
            logger.error(f'LLM API Call Error: {e}. Retrying in {wait_time} seconds...')
            time.sleep(wait_time)
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
            logger.error(f"Unexpected error: {traceback.format_exc()}")
            logger.error('Chat Query Error')
            sys.exit(1)
    logger.error('Max retries exceeded for LLM API calls.')
    sys.exit(1)
            

def query_cache(md5: str):
    cpath = os.path.join(get_prompt_cache_root(), md5)
    if os.path.exists(cpath):
        logger.info(f'Cache Hit\n{cpath}')
        with open(cpath, 'rb') as f:
            return pickle.load(f)
    return None

def save_cache(md5: str, result: str):
    cpath = os.path.join(get_prompt_cache_root(), md5)
    with open(cpath, 'wb') as f:
        pickle.dump(result, f)
    logger.info(f'Cache Saved to: {cpath}')

def build_kwargs(
    msgs,
    mod: ModelHub,
    cfg: Dict[str, int] = {},
    tools: list[dict] = []
):
    msgs = truncate_messages(
        msgs,
        cfg.get('prompt_max_tokens') if cfg else None,
        mod.name()
    )
    kwargs = {
        'platform': mod.get_platform(),
        'model': mod.name(),
        'messages': msgs,
        'max_tokens': mod.value['max_tokens'],
    }
    if tools:
        kwargs['tools'] = tools
    if mod.has_effort():
        kwargs['reasoning_effort'] = mod.get_effort()
 
    if mod.need_budget():
        assert 'budget' in cfg
        assert 'max_tokens' in cfg
        budget = cfg['budget']
        kwargs['extra_body'] = {
            'thinking': {
                "type": "enabled",
                "budget_tokens": budget
            }
        }
    else:
        kwargs['max_tokens'] = min(
            mod.value['max_tokens'],
            cfg.get('max_tokens', 8192)
        )
    return kwargs


def _get_encoder(model_name: str):
    if tiktoken is None:
        return None
    try:
        return tiktoken.encoding_for_model(model_name)
    except Exception:
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None


def _count_tokens(enc, text: str) -> int:
    if enc is None:
        return max(1, len(text) // 4)  # rough fallback
    try:
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def truncate_messages(msgs: List[Dict], max_prompt_tokens: int | None, model_name: str) -> List[Dict]:
    if not max_prompt_tokens or max_prompt_tokens <= 0:
        return msgs
    enc = _get_encoder(model_name)

    def msg_tokens(m):
        # OpenAI counting differs per role, but for truncation an approximate sum is fine
        return _count_tokens(enc, m.get('content', ''))

    if not msgs:
        return msgs

    preserved = []
    rest = msgs
    # Keep system message if present
    if msgs[0].get('role') == 'system':
        preserved = [msgs[0]]
        rest = msgs[1:]

    budget = max_prompt_tokens - sum(msg_tokens(m) for m in preserved)
    if budget <= 0:
        logger.info('Prompt truncation applied: only system message kept')
        return preserved

    kept = []
    for m in rest:  # keep from head to tail until budget exhausted
        tks = msg_tokens(m)
        if tks <= budget:
            kept.append(m)
            budget -= tks
        else:
            break
    truncated = preserved + kept
    if len(truncated) != len(msgs):
        logger.info(
            f'Prompt truncated to ~{max_prompt_tokens} tokens: kept {len(truncated)}/{len(msgs)} messages (head-first)'
        )
    return truncated

@dataclass
class LLMResult:
    message: ChatCompletionMessage
    inp_tokens: int
    out_tokens: int

    def __str__(self):
        ans = ''
        ans += f'[Message]\n{str(self.message.content)}\n\n'
        ans += f'[Tools]\n{str(self.message.tool_calls)}\n\n'
        ans += f'[Input Tokens] {self.inp_tokens}\n'
        ans += f'[Completion Tokens] {self.out_tokens}\n'
        return ans

def _streaming_call_raw(chat, model: str):
    completion = client.chat.completions.create(
        messages=chat.dump(),
        model=model,
        stream=True
    )
    content = ""
    inp_tokens = 0
    oup_tokens = 0
    for chunk in completion:
        delta = chunk.choices[0].delta
        if delta.content is not None:
            content += delta.content
        if chunk.usage is not None:
            inp_tokens = chunk.usage.prompt_tokens
            oup_tokens = chunk.usage.completion_tokens
    
    return LLMResult(
        message=ChatCompletionMessage(
            content=content,
            role="assistant"
        ),
        inp_tokens=inp_tokens,
        out_tokens=oup_tokens
    )

from prompt.util import str_to_model
streaming_cache_root = os.path.join(get_prompt_cache_root(), 'streaming')
def streaming_call(chat: ChatHistory, model: ModelHub):
    md5 = chat.md5(model)
    if os.path.exists(os.path.join(streaming_cache_root, md5)):
        with open(os.path.join(streaming_cache_root, md5), 'rb') as f:
            return pickle.load(f)
    else:
        result = _streaming_call_raw(chat, model.name())
        with open(os.path.join(streaming_cache_root, md5), 'wb') as f:
            pickle.dump(result, f)
        return result

def query_llm_raw(
    msgs: List[Dict],
    mod: ModelHub,
    cfg: Dict[str, int] = {}, 
    tools: list[dict] = [],
    save_name: Optional[str] = None,
):
    logger.info("Debugging: In Query LLM Raw")
    kwargs = build_kwargs(
        msgs, mod, cfg, tools
    )
    response = chat_low_level(**kwargs)
    logger.info("Debugging: After Chat Low Level")
    result = parse_result(response, save_name)
    return response, result

def query_llm_raw_with_cache(
    msgs,
    mod: ModelHub,
    cfg: Dict[str, int] = {},
    tools: list[dict] = [],
    save_name: Optional[str] = None,
    key: Optional[str] = None
):
    if key is not None:
        cached = query_cache(key)
        if cached is not None:
            return cached, parse_result(cached, save_name)
    
    response, result = query_llm_raw(
        msgs, mod, cfg, tools, save_name
    )
    if key is not None:
        save_cache(key, response)
    return response, result

def query_llm(
    chat: ChatHistory,
    mod: ModelHub,
    cfg: Dict[str, int] = {},
    use_disk_cache: bool = True,
    save_name: Optional[str] = None,
    tools: list[dict] = []
):

    val = os.environ.get('PROMPT_CHANCES', '0')
    val = int(val) - 1
    if val < 0:
        logger.error('Prompt Chances Exceeded')
        sys.exit(1)
    os.environ['PROMPT_CHANCES'] = str(val)

    logger.info('Start Querying LLM')
    cached = None
    md5 = "dummy"
    if use_disk_cache:
        md5 = chat.md5(mod)
        cached = query_cache(md5)
    logger.info("Debugging: Finished Checking Cache")

    save_name = save_name if verbose else None
    
    logger.info(f"Debugging: save_name = {save_name}")
    logger.info(f"Debugging: use_disk_cache = {use_disk_cache}")
    logger.info(f"Debugging: Cached = {cached}")

    if cached is not None:
        return parse_result(cached, save_name)

    logger.info(f'Debugging: Before Start Query LLM {mod.name()}')
    response, result = query_llm_raw(chat.dump(), mod, cfg, tools, save_name)
    logger.info(f'Debugging: After Finish Query LLM {mod.name()}')
    
    if use_disk_cache:
        save_cache(md5, response)  
    logger.info(f'Debugging: After Save Cache LLM {mod.name()}')   
    return result

def parse_result(response: ChatCompletion, save_name: str | None) -> LLMResult:
    result = LLMResult(
        message=response.choices[0].message,
        inp_tokens=response.usage.prompt_tokens if response.usage else 0,
        out_tokens=response.usage.completion_tokens if response.usage else 0
    )

    if save_name is not None:
        loc = os.path.join(get_output_dir(), 'prompts', save_name)
        with open(loc, 'w') as f:
            f.write(str(result))

    return result

pid = 0
def add_stamp(chat: ChatHistory):
    global pid
    pid = pid + 1
    chat2 = ChatHistory(chat.dump())
    role, content = chat2.history[-1]
    content += f'\n\n<!--{pid}-->\n'
    chat2.history[-1] = (role, content)
    return chat2

from concurrent.futures import ThreadPoolExecutor as PoolEx
def batch_llm(
    chat: ChatHistory,
    mod: ModelHub,
    cfg: Dict[str, int] = {},
    n_tasks: int = 5,
    use_disk_cache: bool = True
):

    logger.info('Start Batch Query LLM')
    results = []
    tasks = []
    for _ in range(n_tasks):
        chat2 = add_stamp(chat)
        md5 = chat2.md5(mod)
        if use_disk_cache:
            cached = query_cache(md5)
            if cached is not None:
                results.append(cached)
                continue
        kwargs = build_kwargs(chat2, mod, cfg)
        tasks.append((md5, kwargs))

    answers = []
    with PoolEx(max_workers=4) as executor:
        answers = executor.map(
            lambda x: (x[0], chat_low_level(**x[1])), tasks
        )
    """
    for i, (md5, kwargs) in enumerate(tasks):
        logger.info('Batch Querying LLM %d/%d', i, len(tasks))
        response = chat_low_level(**kwargs)
        answers.append((md5, response))
        logger.info('Batch Querying LLM %d/%d Done', i, len(tasks))
    """
    for md5, response in answers:
        result: str = response.choices[0].message.content
        if use_disk_cache: save_cache(md5, result)
        results.append(result)

    return results


def embedding(**kwargs):
    #enc_str = str(
    #    '[Embedding]\n' + 
    #   kwargs.get('input', '') + 
    #    kwargs.get('model', '')
    #)
    #key = hashlib.md5(enc_str.encode('utf-8')).hexdigest()
    #cached = query_cache(key)
    #if cached is not None:
    #    return cached

    logger.info(f'Start Embed')
    platform = kwargs.get('platform', 'litellm')
    del kwargs['platform']
    match platform:
        case 'litellm':
            f = lambda: client.embeddings.create(
                **kwargs
            )
        case 'azure':
            f = lambda: client_azure.embeddings.create(
                **kwargs
            )
        case 'yunwu':
            f = lambda: client_yunwu.embeddings.create(
                **kwargs
            )
        case _:
            assert False
    while True:
        try:
            result = f()
            break
        except:
            logger.error('Embedding Query Error')
            time.sleep(90)

    #save_cache(key, json.dumps(result.model_dump(), indent=4))
    return result

if __name__ == '__main__':
    print('LLM Module', flush=True)
    mod = ModelHub.GPTO4Mini
    ic(mod)
    result = query_llm_raw(
        msgs=[
            {'role': 'system', 'content': 'This is a system message.'},
            {'role': 'user', 'content': 'This is a user message.'}
        ],
        mod=mod,
        cfg={'max_tokens': 1000},
        tools=[]
    )
    ic(result)
