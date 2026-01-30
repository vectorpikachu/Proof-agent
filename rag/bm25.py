import bm25s, os, logging, pickle, sys
from env import cache_root, prover_root
from bm25s.tokenization import Tokenizer
from hashlib import md5
from pathlib import Path
from typing import Literal

my_bm25_cluster = None
logger = logging.getLogger('My BM25')

bm25_cache_home_dir = Path(cache_root) / 'mybm25_cache'
if not bm25_cache_home_dir.exists():
    os.makedirs(bm25_cache_home_dir)

class BM25Collection:
    def __init__(self, docs: list[dict], 
                 doc_field: Literal['lemma_text', 'pfstat_text'],
                 tokenizer: Tokenizer):

        self.empty = len(docs) == 0
        if self.empty:
            return
        self.docs = docs
        self.doc_field = doc_field
        corpus = [doc[doc_field] for doc in docs]
        tokenized = tokenizer.tokenize(corpus)
        self.bm25 = bm25s.BM25()
        self.bm25.index((tokenized, tokenizer.get_vocab_dict()))
        
    def retrieval(self, query: str, topk: int, output_fields: list[str],
                  tokenizer: Tokenizer):
        if self.empty:
            return []
        tokens = tokenizer.tokenize(query.strip(), update_vocab=False)
        topk = min(topk, len(self.docs))
        results, scores = self.bm25.retrieve(tokens, k=topk)
        #print(scores, doc_ids)
        result = []
        for i in range(results.shape[1]):
            doc_id, score = results[0, i], scores[0, i]
            cur_result = {
                'entity': {
                    k: self.docs[doc_id][k] for k in output_fields
                },
                'distance': score
            }
            result.append(cur_result)

        return result

class BM25Cluster:
    def __init__(self, docss: list[tuple[str, list[dict]]],
                 doc_field: Literal['lemma_text', 'pfstat_text'],
                 name: str):

        self.name = name
        all_docs = []
        for (_, docs) in docss:
            all_docs += docs
        self.tokenizer = Tokenizer(splitter=r"\S+")
        corpus = [doc[doc_field] for doc in all_docs]
        self.tokenizer.tokenize(corpus)
        self.bm25s: dict[str, BM25Collection] = {}
        for (path, docs) in docss:
            #print('add path', path)
            self.bm25s[path.strip()] = BM25Collection(docs, 
                                                      doc_field, 
                                                      self.tokenizer)
        
    def retrieval(self, path: str, data: str, limit: int, 
                  output_fields: list[str]):
        if path not in self.bm25s:
            print(path, self.name, self.bm25s.keys())
            logger.error(f'My BM25 path not found: {path}')
            assert False
        return self.bm25s[path].retrieval(data, limit, 
                                          output_fields, self.tokenizer)


def init_cluster(visible_paths: list[str], mpath: str, mindex: int, 
                 k1: float = 1.5, b: float = 0.75):

    visible_paths = list(visible_paths)

    lemma_vecs: list[dict] = []
    pfstat_vecs: list[dict] = []
    with open(Path(prover_root) / "rag/lemma_vecs.pkl", "rb") as f:
        lemma_vecs, _ = pickle.load(f)
    with open(Path(prover_root) / "rag/pfstat_vecs.pkl", "rb") as f:
        pfstat_vecs, _ = pickle.load(f)

    pfstat_docss = []
    for path in ([mpath] + visible_paths):
        docs = []
        index_limit = mindex if path == mpath else 1000000
        
        for pfstat in pfstat_vecs:
            if (pfstat.get('pfstat_path', '') == path and 
                pfstat.get('index', index_limit) < index_limit):
                new_text: str = pfstat['pfstat_text']
                key = "** [Current Focused Goal] **"
                if new_text.find(key) != -1:
                    new_text = new_text[new_text.find(key)+len(key):]
                pfstat['pfstat_text'] = new_text.lstrip().rstrip()
                docs.append(pfstat)

        pfstat_docss.append((path, docs))
    
    pfstat_cluster = BM25Cluster(pfstat_docss, 'pfstat_text', 'pfstat')


    lemma_docss = []
    for path in visible_paths:
        docs = []
        for lemma in lemma_vecs:
            if lemma.get('lemma_path', '') == path:
                docs.append(lemma)

        #print(path, docs)
        lemma_docss.append((path, docs))
    
    #sys.exit(1)
    lemma_cluster = BM25Cluster(lemma_docss, 'lemma_text', 'lemma')


    global my_bm25_cluster
    my_bm25_cluster = {
        'lemma': lemma_cluster,
        'pfstat': pfstat_cluster
    }


class MyBM25Client:
    def __init__(self):
        pass
    def search(
        self,
        collection_name: str,
        data,
        limit: int,
        **kwargs
    ):
        if my_bm25_cluster is None:
            raise ValueError('BM25 cluster not initialized')

        output_fields = kwargs.get('output_fields', None)
        filter_path: str = kwargs.get('filter', None)
        if filter_path is None or output_fields is None:
            return [[]]

        path = filter_path[filter_path.find("_path == '") + 10:]
        path = path[:path.find("'")]
        path = path.strip()
        
        name = 'lemma' if collection_name.find('LEMMA') != -1 else 'pfstat'

        return [my_bm25_cluster[name].retrieval(
            path,
            data[0],
            limit,
            output_fields
        )]
    

    