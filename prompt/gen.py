from typing import List, Dict, Tuple, Union
from string import Template
from env import verbose, get_output_dir
from prompt.util import ChatHistory
import sys, os, logging, re

from rag.query import QueryParam, get_examples, get_lemmas
from rag.infra import execute

from prompt.templates import (
    system_prover,
    task_prover,
    ContextItem,
    mk_prompt,
    pretty,
    format_list,
)

logger = logging.getLogger('GenPromptInternal')


def convert_proof_state(proof_state):
    """
    将Coq的proof state转换为命题形式
    """
    if not proof_state or proof_state.strip() == "No current goal":
        return "No current goal"
    
    # 分割proof state为上下文和目标部分
    lines = proof_state.strip().split('\n')
    context_lines = []
    goal_lines = []
    separator_found = False
    
    for line in lines:
        if line.strip().startswith('=') and '=' in line:  # 检测分隔线
            separator_found = True
            continue
        if not separator_found:
            context_lines.append(line.strip())
        else:
            if line.strip():  # 忽略空行
                goal_lines.append(line.strip())
    
    goal_str = ' '.join(goal_lines)  # 合并目标行
    
    # 解析上下文
    variables = []  # 存储变量和类型
    hypotheses = []  # 存储假设表达式
    
    for line in context_lines:
        if ':' not in line:
            continue
        parts = line.split(':', 1)
        left = parts[0].strip()
        right = parts[1].strip()
        
        # 判断是否是变量声明（类型是简单标识符）
        if re.match(r'^\w+$', right) or right in ['Z', 'int', 'nat', 'bool']:
            variables.append((left, right))
        else:
            hypotheses.append(right)  # 添加假设表达式
    
    # 解析目标中的全称量词和蕴含
    goal_vars = []  # 目标中引入的变量
    goal_hyps = []  # 目标中的前提条件
    conclusion = goal_str  # 默认结论是整个目标
    
    # 匹配全称量词: forall var : type, ...
    forall_match = re.match(r'^\s*forall\s+(\w+)\s*:\s*(\w+)\s*,\s*(.*)$', goal_str)
    if forall_match:
        var_name = forall_match.group(1)
        var_type = forall_match.group(2)
        goal_vars.append((var_name, var_type))
        remaining = forall_match.group(3)
        
        # 解析蕴含式: A -> B -> ... -> conclusion
        parts = [p.strip() for p in remaining.split('->')]
        if len(parts) > 1:
            goal_hyps = parts[:-1]  # 所有前提条件
            conclusion = parts[-1]   # 最终结论
    
    # 合并所有变量和假设
    all_vars = variables + goal_vars
    all_hyps = hypotheses + goal_hyps
    
    # 构建命题字符串
    # 全称量化部分
    proposition = "forall "
    proposition += " ".join([f"({var} : {typ})" for var, typ in all_vars])
    proposition += ",\n"
    
    for hyp in all_hyps:
        proposition += f"{hyp} ->\n"
    proposition += conclusion
    
    return proposition


class PromptInfo:
    def __init__(self, cfg: Dict = {}):
        self.help_info = cfg['help_info']
        self.__init_defs(cfg.get('definitions', []))
        self.failing_trials = cfg['failing_trials']
        self.workspace = cfg['workspace']
        self.verified_steps = cfg['verified_steps']
        self.use_examples = cfg.get('use_examples', True)
        
        # Handle both GoalState objects and dictionaries
        last_goal = cfg['last_goal']
        if hasattr(last_goal, 'raw'):  # GoalState object
            self.goal_raw = last_goal.raw
            self.goal_init = last_goal.init
            self.goal_moved = last_goal.moved
        else:  # Dictionary (for backward compatibility)
            self.goal_raw = last_goal['raw']
            self.goal_init = last_goal['init']
            self.goal_moved = last_goal['moved']
        
        self.vpaths = cfg['visible_paths']
        self.mpath = cfg['mpath']
        self.mindex = cfg['mindex'] - 1
        print(cfg['workspace'])
        if 'bb5' in cfg['workspace'] or 'pnvrocqlib' in cfg['workspace']:
            self.mindex -= 1
        self.try_subterm = False
        self.legacy_text = cfg['legacy_text']
        #print(os.environ['COMMENT'])
        self.use_doc = os.environ['COMMENT'] == 'True'
        #print('DOC =', self.use_doc)
        self.max_fetch = cfg.get('max_fetch', 8)
        self.use_print_tool = cfg.get('use_def_tool', False)
        self.use_proposition_form = cfg.get('use_proposition_form', False)
        self.model = cfg.get('model', '')

        self.help_info['retrieval_method'] = cfg.get(
            'retrieval_method', 'dense'
        )
        self.round_no = cfg['round']
        
        self.__init_rag('rag_' + str(cfg['round']) + '.txt')
    def __init_rag(self, save_name):
        if self.help_info['retrieval_method'] == 'none':
            qitems = []
        else:
            query_param = QueryParam(
                goal=self.goal_init,
                goal_move=self.goal_moved,
                limit=self.max_fetch,
                visible_paths=self.vpaths.get('workspace', []),
                mpath=self.mpath,
                mindex=self.mindex,
                defs=self.help_info.get('defs', ''),
                trials=self.help_info.get('trials', ''),
                use_doc=self.use_doc,
                use_history=self.help_info.get('with_history', False),
                round_no=self.round_no,
                model=self.model,
                retrieval_method=self.help_info['retrieval_method'],
            )

            qitems = []
            qitems += get_examples(query_param)
            qitems += get_lemmas(query_param)

        allresult = []
        if len(qitems) > 0:
            allresult = execute(qitems)
            

        if verbose:
            with open(
                f'{get_output_dir()}/rag-query-results/{save_name}', 
                'w'
            ) as f:
                f.write(pretty(sorted(allresult)))
                f.flush()
            #sys.exit(1)

        capacity_examples = 25000 if self.use_examples else 0
        capacity_lemmas = 3000 if self.use_examples else 28000
        self.lemmas = []
        self.examples= []
        for candid in sorted(allresult):
            if capacity_examples <= 0 and capacity_lemmas <= 0:
                break

            if candid.category == 0:
                if capacity_lemmas <= 0:
                    continue
    
                text = candid.data['text']
                comment = candid.data['def_text_ans_noreason']
                with_comment_doc = f'(*\n{comment}\n*)\n'
                data_docstring = '' if not self.use_doc else with_comment_doc
                citem = ContextItem(
                    '',
                    maxlength=1024,
                    content = (
                        '```coq\n' +
                        f'{text}\n' +
                        data_docstring +
                        '```\n\n'
                     )
                )
                capacity_lemmas -= citem.render_len()
                if not self.use_doc:
                    capacity_lemmas -= len(with_comment_doc)
                if capacity_lemmas >= 0:
                    self.lemmas.append(citem)

            elif candid.category == 1:
                if capacity_examples <= 0:
                    continue

                with_comment_doc = '\n\n- Strategy:\n\n' + candid.data['def_goal_proof_ans_noreason']
                data_docstring = '' if not self.use_doc else with_comment_doc

                citem = ContextItem(
                    '',
                    maxlength=4096,
                    content = (
                        '- Proof State:\n\n' +
                        candid.data['goal'] +
                        '\n\n- Proof:\n\n' +
                        candid.data['proof'] +
                        data_docstring
                     )
                )

                capacity_examples -= citem.render_len()
                if not self.use_doc:
                    capacity_examples -= len(with_comment_doc)
                if capacity_examples >= 0:
                    self.examples.append(citem)

    def __init_defs(self, def_list):
        self.definitions = list(map(
            lambda x: ContextItem(x[0], '```coq\n' + x[1] + '\n```\n'),
            def_list
        ))

        self.help_info['defs'] = format_list(
            self.definitions, 'Definition'
        )


    def upd_def(self, def_list, save_name):
        self.__init_defs(def_list)
        self.__init_rag(save_name)

    def gen_chat(
        self,
        system_prompt: str = system_prover,
        user_template: Template = task_prover,
        **extra_args
    ):

        return ChatHistory([
            {'role': 'system', 
             'content': system_prompt},
            {'role': 'user', 
             'content': self.user_prompt(user_template, **extra_args)},
        ])

    def user_prompt(
        self,
        template: Template = task_prover,
        **extra_args
    ):
        # 准备基本的prompt数据
        prompt_data = {
            'proof_status': self.goal_init, #self.goal_init,
            'definitions': self.definitions,
            'lemmas': self.lemmas,
            'examples': self.examples,
            'failing_trials': self.failing_trials[-22000:],
            'original_goal': extra_args.get('original_goal', ''),
            'verified_text': extra_args.get('verified_text', ''),
        }
        
        # 如果启用命题形式，添加转换后的命题
        if self.use_proposition_form:
            try:
                proposition_form = convert_proof_state(self.goal_init)
                prompt_data['proposition_form'] = f"""### Proposition Form
<!-- Alternative representation of the proof goal as a mathematical proposition -->

```text
{proposition_form}
```
"""
            except Exception as e:
                logger.warning(f"Failed to convert proof state to proposition: {e}")
                prompt_data['proposition_form'] = ''
        else:
            prompt_data['proposition_form'] = ''

        prompt = mk_prompt(True, prompt_data, template)
        return prompt

    def debug(self, name: str, 
              system_file = 'system_prove.md',
              system: str = system_prover,
              template: Template = task_prover):

        logger.info('Start Debug')
        loc = f'{get_output_dir()}/prompts/prompt_{name}.md'
        with open(f'{get_output_dir()}/{system_file}', 'w') as f:
            f.write(system)
        with open(loc, 'w') as f:
            f.write(self.user_prompt(template))
            f.flush()      