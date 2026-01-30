from prompt.util import str_to_model
import json

basic_config = {
    'model': 'GPTO4Mini',
    'retrieval_method': 'dense',
    'max_explore_limit': 5,
    'llm_config': {
        'max_tokens': 128000,
        'budget': 100000,
        # Optional: cap prompt tokens before sending to the model
        # (prompt truncation keeps the system message and the most recent turns)
        'prompt_max_tokens': None
    },
    'enable_hammer': True,
    'use_cache': True,
    'instr': [],
    'max_prompt': 81,
    'max_iter': 27,
    'in_test': False,
    'use_docstring': True,
    'use_simple_mode': False,
    'max_decision_num': 5,
    'use_history': True,
    'cold_start_threshold': 10000,
    'use_print_tool': False,
    'tool_call_limit': 0,
    'use_proposition_form': False,
    'enable_branch_check': False,
    "o3_call_limit": 0,
    "eval_call_limit": 0,
    "retain_legacy_text_cont": False,
    "extra_bad_keywords": [],
    "scratch_everytime": False,
    "use_examples": True
}

def load_with_basic_config(config_loc: str):
    with open(config_loc, 'r') as f:
        config = json.load(f)
    if not isinstance(config, dict):
        raise ValueError(f"Config file {config_loc} shall be dict.")

    for key, value in basic_config.items():
        if isinstance(value, dict):
            if key not in config:
                config[key] = {}
            for sub_key, sub_value in value.items():
                if sub_key not in config[key]:
                    config[key][sub_key] = sub_value
        elif key not in config:
            config[key] = value

    config['model'] = str_to_model(config['model'])
    config['llm_config']['max_tokens'] = min(
        config['llm_config']['max_tokens'],
        config['model'].value['max_tokens']
    )

    config['use_docstring'] = config.get('use_doc', True)

    return config

class HyperParams:
    def __init__(self, config_loc: str):
        self.config = load_with_basic_config(config_loc)
