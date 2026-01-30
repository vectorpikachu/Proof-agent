from prompt.llm import query_llm, client, embedding, streaming_call
from prompt.util import ChatHistory, Role, ModelHub
from prompt.templates import (
    fill_template,
    system_prompts,
    tasks
)
from logging import getLogger
import sys, os
from env import get_output_dir

logger = getLogger('Prompt-Document')
systems_pfstate_emb = system_prompts['pfstate_emb']
systems_lemma_emb = system_prompts['lemma_emb']
tasks_emb = tasks['embedding']

from tiktoken import encoding_for_model
def truncate_doc(doc, max_token_len=8191):
    enc = encoding_for_model('text-embedding-3-large')
    tokens = enc.encode(doc)[:max_token_len]
    return enc.decode(tokens)

def lemma_emb(
    goal: str, 
    use_doc: bool, 
    with_history: bool,
    defs: str,
    trials: str,
    round_no: int,
    model: str
):
    if use_doc:
        system = systems_lemma_emb[with_history]
        user = fill_template(
            tasks_emb[with_history], {
                '_blank': '',
                'goal': goal,
                'defs': defs,
                'trials': trials,
            }
        )

        chat = ChatHistory([])
        chat._add_msg(Role.SYSTEM, system)
        chat._add_msg(Role.USER, user)
        result = streaming_call(chat, model)
        doc = result.message.content
        if doc is None:
            doc = ""
        with open(os.path.join(
            get_output_dir(),
            "prompts",
            'lemma_emb_' + str(round_no) + '.md'
        ), 'w') as f:
            f.write(
                f'[System]\n\n{system}\n\n[User]\n\n{user}\n\n{str(result)}'
            )

        doc = doc[doc.find('<lemma>') + 7 : doc.find('</lemma>')]
        doc = doc.strip()
        print(doc, flush=True)
        #print('=' * 50)
        #print(system)
        #print(user)
        #print(doc)
        goal = 'Below is a Coq lemma query:\n' + doc
#        goal = truncate_doc(goal)
#        logger.info('LLM Result:\n' + goal)
#   
    emb = embedding(
        model='yunwu/text-embedding-3-large',
        input=goal,
        platform='litellm'
    )
    vec = emb.model_dump()['data'][0]['embedding']
    #logger.log(15, f'pfstat_emb = {vec}')
    #sys.exit(1)
    return vec

def pfstat_emb(
    goal: str,
    use_doc: bool,
    with_history: bool,
    defs: str,
    trials: str,
    round_no: int,
    model: str
):

    if use_doc:
        system = systems_pfstate_emb[with_history]
        user = fill_template(
            tasks_emb[with_history], {
                '_blank': '',
                'goal': goal,
                'defs': defs,
                'trials': trials,
            }
        )
        chat = ChatHistory([])
        chat._add_msg(Role.SYSTEM, system)
        chat._add_msg(Role.USER, user)
        print('Start Streaming Call', flush=True)
        result = streaming_call(chat, model)
        doc = result.message.content
        print("[DOC]", doc, sep='\n', flush=True)
        if doc is None:
            doc = ""
        with open(os.path.join(
            get_output_dir(),
            "prompts",
            "pfstat_emb_" + str(round_no) + '.md'
        ), 'w') as f:
            f.write(
                f'[System]\n\n{system}\n\n[User]\n\n{user}\n\n{str(result)}' + '\n\n' + doc
            )

        goal = 'Below is the proof idea:\n' + goal + '\n' + doc
        goal = truncate_doc(goal)
#        logger.info('LLM Result:\n' + goal)
#        sys.exit(1)
    
    emb = embedding(
        model='yunwu/text-embedding-3-large',
        input=goal,
        platform='litellm'
    )
    vec = emb.model_dump()['data'][0]['embedding']
    #logger.log(15, f'pfstat_emb = {vec}')
    #sys.exit(1)
    return vec