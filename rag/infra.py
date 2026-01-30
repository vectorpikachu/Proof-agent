import sys
if __name__ == '__main__':
    sys.path[0] = '/home/lhz/PLResearch/coq-agent'

import os, hashlib, pickle, traceback
from pymilvus import MilvusClient
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import cpu_count
from logging import getLogger
from env import cache_root
from dataclasses import dataclass
from prompt.doc import lemma_emb, pfstat_emb
from rag.bm25 import MyBM25Client
from prompt.util import ModelHub

logger = getLogger('QueryInternal')
knn_cache_home_dir = os.path.join(cache_root, 'knn_cache')
bm25_cache_home_dir = os.path.join(cache_root, 'bm25_cache_3072')
if not os.path.exists(bm25_cache_home_dir):
    os.makedirs(bm25_cache_home_dir)
if not os.path.exists(knn_cache_home_dir):
    os.makedirs(knn_cache_home_dir)

client = None
cpu_max = 1

def __register(mode='dense'):
    global client
    if mode == 'mybm25':
        client = MyBM25Client()
    elif mode == 'dense-1024':
        logger.info('Registering Dense-1024 client')
        client = MilvusClient(
            uri='https://in03-9910f8af57cf275.serverless.gcp-us-west1.cloud.zilliz.com',
            token='049e3ee484b1d7664c5253ef7ebd50cfa3c01526846552a47097d81771c3e272bcb5dcc2fcf0588810ace2cd3d68cbec72fe3d4d',
        )
    elif mode == 'dense' or mode== 'bm25':
        logger.info('Registering Dense-3072 Client')
        client = MilvusClient(
            uri='https://in05-a412221ce3e7b0e.serverless.gcp-us-west1.cloud.zilliz.com',
            token='049e3ee484b1d7664c5253ef7ebd50cfa3c01526846552a47097d81771c3e272bcb5dcc2fcf0588810ace2cd3d68cbec72fe3d4d',
        )

@dataclass
class QueryParam:
    goal: str
    goal_move: str
    limit: int
    mpath: str
    mindex: int
    defs: str
    trials: str
    visible_paths: list[str]
    use_doc: bool
    use_history: bool
    round_no: int
    model: str
    retrieval_method: str = 'dense'

    def gen_vec(self, category):
        if self.retrieval_method != 'dense':
            return self.goal

        if category == 0:
            return lemma_emb(
                self.goal,
                self.use_doc,
                self.use_history,
                self.defs,
                self.trials,
                self.round_no,
                self.model
            )
        else:
            return pfstat_emb(
                self.goal,
                self.use_doc,
                self.use_history,
                self.defs,
                self.trials,
                self.round_no,
                self.model
            )


class QueryResult:
    def __init__(self, col: str, category: int, data: dict):
        self.col = col
        self.category = category
        self.data = data['entity']
        self.distance = data['distance']

    def __lt__(self, other):
        return self.distance > other.distance
    
    def __str__(self):
        return f'[QueryResult]\ncol={self.col}\ncategory={self.category}\ndata={self.data}\ndistance={self.distance}'

class QueryItem:
    def __init__(
        self, 
        col: str, 
        data: List, 
        category: int,
        limit: int = 8,
        anns_field: Optional[str] = None,
        mode: str = 'dense',
        filter: Optional[str] = None,          
        output_fields: Optional[List[str]] = None
    ):
        self.col = col
        self.data = data
        self.limit = limit
        self.filter = filter
        self.category = category
        self.output_fields = output_fields
        self.mode = mode
        self.anns_field = anns_field if anns_field is not None else ''
    
    def __str__(self):
        return f'[QueryItem]\ncol={self.col}\ndata=...\nlimit={self.limit}\nfilter={self.filter}\ncategory={self.category}\noutput_fields={self.output_fields}\nsearch_field={self.anns_field}'
    
    def str_full(self):
        return f'[QueryItem]\ncol={self.col}\ndata={self.data}\nlimit={self.limit}\nfilter={self.filter}\ncategory={self.category}\noutput_fields={self.output_fields}\nsearch_field={self.anns_field}'
    
    
    def md5(self):
        return hashlib.md5(self.str_full().encode()).hexdigest()
    
    def gen_query_dense(self) -> QueryResult:
        md5 = self.md5()
        cpath = os.path.join(knn_cache_home_dir, md5)
        if os.path.exists(cpath):
            with open(cpath, 'rb') as f:
                logger.info(f'knn cache hit {md5}')
                pass#return pickle.load(f)
        global client
        logger.info(f'knn cache miss {md5}')
        try:
            #print(self.data)
            #import sys
            #sys.exit(1)
            topK = client.search(
                collection_name=self.col,
                data=self.data,
                limit=self.limit,
                anns_field=self.anns_field,
                filter=self.filter,
                output_fields=self.output_fields,
                search_params={
                    "ef": 240
                }
            )[0]
            #print(self.filter)
            #print('topK =', topK)
            result = [
                QueryResult(self.col, self.category, candid) 
                for candid in topK
            ]
            with open(cpath, 'wb') as f:
                pickle.dump(result, f)
            logger.info(f'knn cache save {md5}')
            return result

        except Exception as e:
            logger.error(f'Search get error: {e}')
            logger.error(traceback.format_exc())
            assert False

    def gen_query_bm25(self) -> QueryResult:
        md5 = self.md5()
        cpath = os.path.join(bm25_cache_home_dir, md5)
        if os.path.exists(cpath):
            with open(cpath, 'rb') as f:
                logger.info(f'bm25 cache hit {md5}')
                return pickle.load(f)
        global client
        logger.info(f'bm25 cache miss {md5}')
        try:
            topK = client.search(
                collection_name=self.col,
                data=self.data,
                anns_field='sparse',
                limit=self.limit,
                filter=self.filter,
                output_fields=self.output_fields,
                search_params={
                    "params": {
                        "drop_ratio_search": 0.2
                    }
                }
            )[0]
            result = []
            for candid in topK:
                result.append(QueryResult(
                    self.col, self.category, candid  
                ))
            with open(cpath, 'wb') as f:
                pickle.dump(result, f)
            logger.info(f'bm25 cache save {md5}')
            return result
        except Exception as e:
            logger.error(f'BM25 Search get error: {e}')
            logger.error(traceback.format_exc())
            assert False
            return []
        
    def gen_query_mybm25(self) -> QueryResult:
        global client
        try:
            topK = client.search(
                collection_name=self.col,
                data=self.data,
                limit=self.limit,
                filter=self.filter,
                output_fields=self.output_fields,
            )[0]
            result = []
            for candid in topK:
                result.append(QueryResult(
                    self.col, self.category, candid  
                ))
            return result
        except Exception as e:
            logger.error(f'My BM25 Search get error: {e}')
            logger.error(traceback.format_exc())
            assert False
            return []
        
    def gen_query(self) -> QueryResult:
        if self.mode == 'mybm25':
            return self.gen_query_mybm25()
        elif self.mode == 'dense':
            return self.gen_query_dense()
        elif self.mode == 'bm25':
            return self.gen_query_bm25()
        else:
            raise ValueError(f'Unknown mode {self.mode}')
def gen_query(x: QueryItem):
    return x.gen_query()

def execute(pool: List[QueryItem]) -> List[QueryResult]:
    global client
    if client is None: __register(pool[0].mode)
    with ThreadPoolExecutor(max_workers=cpu_max) as executor:
        tmp = executor.map(gen_query, pool)
        ans = []
        for w in tmp: ans += w
        return ans

if __name__ == '__main__':
    os.environ['COMMENT'] = 'True'
    queries = [
        QueryItem(
            col='col_proof',
            data=[[0.01 for _ in range(3072)]],
            filter="path=='/home/syc/CoqStoq_backup/test-repos/compcert/backend/Deadcodeproof.v' && index < 150",
            category=1,
            limit=3,
            anns_field = 'vec_proof_idea_only'
        ),
        QueryItem(
            col='col_lemma',
            data=[[0.01 for _ in range(3072)]],
            filter="path=='/home/syc/CoqStoq_backup/test-repos/compcert/backend/Deadcodeproof.v' && index < 120",
            category=1,
            limit=3,
            anns_field='vec_lemma_text'
        )

    ]
    for i in execute(queries): print(i, flush=True)