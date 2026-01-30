from typing import List
from prompt.templates import ContextItem
from logging import getLogger
from rag.infra import QueryItem, QueryParam

logger = getLogger('RAGQueryInternal')

def get_examples(param: QueryParam) -> List[ContextItem]:
    if param.goal == '': return []
    category = 1
    output_fields = [
        'proof',
        'goal',
        'def_goal_proof_ans_noreason',
        'def_goal_ans_noreason',
        'index',
        'path'
    ]
    ann_field = 'vec_proof_idea_only'
    col_name = 'col_proof'
    if param.retrieval_method == 'bm25':
        col_name += '_bm25'
    method = param.retrieval_method

    logger.info('Start Get Examples')
    logger.info('Goal=\n' + param.goal)
    query_vec = param.gen_vec(category)

    qitems = []
    for path in param.visible_paths:
        qitems.append(QueryItem(
            col_name,
            [query_vec],
            mode=method,
            limit=param.limit,
            anns_field=ann_field,
            filter=f"path == '{path}'",
            category=category,
            output_fields=output_fields
        ))

    qitems.append(QueryItem(
        col_name,
        [query_vec],
        mode=method,
        limit=param.limit,
        category=category,
        filter=f"path == '{param.mpath}' and index < {param.mindex + 1}",
        output_fields=output_fields,
        anns_field=ann_field
    ))

    logger.info('End Get Examples')
    return qitems

def get_lemmas(param: QueryParam) -> List[ContextItem]:
    if param.goal == '': return []
    category = 0
    output_fields = [
        'text',
        'path',
        'def_text_ans_noreason',
    ]
    anns_field = 'vec_lemma_text'
    method = param.retrieval_method
    col_name = 'col_lemma'
    if param.retrieval_method == 'bm25':
        col_name += '_bm25'

    logger.info('Start Get Lemmas')
    query_vec = param.gen_vec(category)

    qitems = []
    for path in param.visible_paths:
        qitems.append(QueryItem(
            col_name,
            [query_vec],
            mode=method,
            limit=param.limit,
            filter=f"path == '{path}'",
            category=category,
            anns_field=anns_field,
            output_fields=output_fields
        ))

    qitems.append(QueryItem(
        col_name,
        [query_vec],
        mode=method,
        limit=param.limit,
        filter=f"path == '{param.mpath}' and index < {param.mindex + 1}",
        category=category,
        anns_field=anns_field,
        output_fields=output_fields
    ))


    logger.info('End Get Lemmas')

    return qitems
