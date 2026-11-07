"""Read-only KEPCO vector reuse, filtered to the caller's verified source allowlist.

No gold questions, answers, labels, employee profiles, environment files or database
clients are read here. Query vectors come from a separately identified loopback
K:LINK encoder. Original document vectors are never modified or regenerated.
"""
from __future__ import annotations

from collections import OrderedDict
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import threading
import urllib.request
from urllib.parse import urlsplit

import numpy as np

WORKSPACE=Path(__file__).resolve().parents[2]
SOURCE=WORKSPACE/'outputs/kepco_hr_full_20261102'
INDEX=WORKSPACE/'outputs/kepco_hr_full_eval_960_20261102/indexes'
MODEL='BAAI/bge-m3'
REVISION='5617a9f61b028005a4858fdac845db406aefb181'
WEIGHTS='993b2248881724788dcab8c644a91dfd63584b6e5604ff2037cb5541e1e38e7e'
APP_ID='klink-kepco-query-encoder-20261107'


class VectorUnavailable(ValueError):
    pass


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def endpoint():
    value=os.getenv('KLINK_HR_ENCODER_URL','http://127.0.0.1:8841').rstrip('/')
    try:
        parsed=urlsplit(value)
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
            raise ValueError()
        if not parsed.port or not 1024<=parsed.port<=65535:raise ValueError()
    except ValueError:
        raise VectorUnavailable('K:LINK 한전 전용 로컬 검색 연결을 확인해야 해요.') from None
    return value


def request(path,payload=None):
    req=urllib.request.Request(endpoint()+path,data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode(),
        headers={} if payload is None else {'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=3 if payload is None else 60) as response:value=json.load(response)
    except Exception:
        raise VectorUnavailable('한전 의미 검색 서비스가 준비되지 않아 답변을 보류했어요.') from None
    if any(value.get(k)!=v for k,v in dict(app_id=APP_ID,model=MODEL,revision=REVISION,weights_sha256=WEIGHTS,dimension=1024).items()):
        raise VectorUnavailable('다른 프로젝트 또는 다른 모델의 검색 연결은 사용하지 않아요.')
    return value


class VectorIndex:
    def __init__(self,sources,corpus_path):
        if Path(corpus_path).resolve()!=(SOURCE/'data/reviewed_units.jsonl').resolve():
            raise VectorUnavailable('KTCS의 고정된 한전 원문과 연결된 벡터만 사용할 수 있어요.')
        meta=json.loads((INDEX/'windows_vectors.json').read_text(encoding='utf-8'))
        if (meta.get('model')!=MODEL or meta.get('revision')!=REVISION or meta.get('weights_sha256')!=WEIGHTS or
            meta.get('dimension')!=1024 or meta.get('truncation') is not False or meta.get('normalized') is not True or
            meta.get('source_sha256')!=sha(corpus_path) or meta.get('vectors_sha256')!=sha(INDEX/'windows.npy') or
            meta.get('windows_sha256')!=sha(SOURCE/'indexes/windows.jsonl')):
            raise VectorUnavailable('원문 버전과 임베딩 인덱스의 일치를 확인하지 못했어요.')
        windows=[json.loads(line) for line in (SOURCE/'indexes/windows.jsonl').read_text(encoding='utf-8').splitlines()]
        if meta.get('ids')!=[w['id'] for w in windows] or len({w['id'] for w in windows})!=len(windows):
            raise VectorUnavailable('원문과 벡터의 순서를 확인하지 못했어요.')
        full=np.load(INDEX/'windows.npy',mmap_mode='r',allow_pickle=False)
        if full.shape!=(len(windows),1024) or full.dtype!=np.float32 or not np.isfinite(full).all():
            raise VectorUnavailable('임베딩 배열 형식을 확인하지 못했어요.')
        allowed={s['id']:s for s in sources}
        selected=[i for i,w in enumerate(windows) if w['unit_record_id'] in allowed]
        for i in selected:
            w=windows[i];s=allowed[w['unit_record_id']]
            if (not w.get('retrieval_only') or w['source_file_sha256']!=s.get('source_file_sha256') or
                not 0<=w['start']<w['end']<=len(s['text']) or
                hashlib.sha256(s['text'][w['start']:w['end']].encode()).hexdigest()!=w['text_sha256']):
                raise VectorUnavailable('허용한 원문과 검색 조각의 연결이 일치하지 않아요.')
        self.vectors=np.asarray(full[selected])
        if not selected or np.max(np.abs(np.linalg.norm(self.vectors,axis=1)-1))>1e-4:
            raise VectorUnavailable('임베딩 정규화 상태를 확인하지 못했어요.')
        self.ids=[windows[i]['unit_record_id'] for i in selected]
        if set(self.ids)!=set(allowed):raise VectorUnavailable('허용 원문 일부에 연결된 벡터가 없어요.')
        self.source_count=len(allowed)
        self.cache=OrderedDict()
        self.lock=threading.Lock()

    def query(self,question):
        digest=hashlib.sha256(question.encode()).hexdigest()
        with self.lock:
            if digest in self.cache:
                vector=self.cache.pop(digest);self.cache[digest]=vector
                return vector
            health=request('/health')
            if (health.get('ready') is not True or health.get('numeric_reference_state')!='PASSED' or
                health.get('parameter_readback_passed') is not True or health.get('resident_encoder_layer_count')!=24):
                raise VectorUnavailable('한전 검색 모델의 원본 가중치 검증을 확인해야 해요.')
            result=request('/embed',dict(text=question))
            vector=np.asarray(result.get('vector'),dtype=np.float32)
            if vector.shape!=(1024,) or not np.isfinite(vector).all() or abs(float(np.linalg.norm(vector))-1)>1e-4:
                raise VectorUnavailable('질문의 임베딩 형식을 확인하지 못했어요.')
            self.cache[digest]=vector
            if len(self.cache)>256:self.cache.popitem(last=False)
            return vector

    def score(self,vector):
        scores={}
        for rid,value in zip(self.ids,self.vectors@vector):scores[rid]=max(scores.get(rid,float('-inf')),float(value))
        return scores

    def search(self,question):
        return self.score(self.query(question))


_loaded=None
_loaded_key=None
_lock=threading.Lock()


def get_index(sources,corpus_path):
    global _loaded,_loaded_key
    key=(str(corpus_path),Path(corpus_path).stat().st_mtime_ns,tuple((s['id'],s['sha256']) for s in sources))
    with _lock:
        if _loaded_key!=key:
            try:loaded=VectorIndex(sources,corpus_path)
            except VectorUnavailable:raise
            except Exception:raise VectorUnavailable('한전 전용 로컬 임베딩 파일을 확인해야 해요.') from None
            _loaded,_loaded_key=loaded,key
    return _loaded


def fuse(lexical_ids,dense_scores,k=10,lexical_weight=1.0):
    dense_ids=sorted(dense_scores,key=lambda rid:(-dense_scores[rid],rid))
    scores={rid:0. for rid in dense_scores}
    for ranking,weight in [(lexical_ids,lexical_weight),(dense_ids,1.)]:
        for rank,rid in enumerate(ranking[:100],1):
            if rid in scores:scores[rid]+=weight/(k+rank)
    return scores
