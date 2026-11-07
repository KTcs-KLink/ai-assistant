"""Dedicated K:LINK query encoder using verified, read-only KEPCO BGE code/weights.

No .env, database, employee profile or document ingestion. All new control output
stays under this checkout's .demo-logs, never the original experiment directory.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

REPO=Path(__file__).resolve().parents[1]
WORKSPACE=REPO.parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8841)
    args=parser.parse_args()
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',args.port))==0:raise SystemExit('Encoder port is occupied; no other process is stopped.')
    sys.stdout.reconfigure(encoding='utf-8')
    old=WORKSPACE/'chat/kepco_hr_full_eval_960_20261102/encode_full.py'
    if hashlib.sha256(old.read_bytes()).hexdigest()!='871169eaaa54561495fd54a21b40d192f29f72d0017ae7a512a854203c99dc5c':
        raise SystemExit('Verified KEPCO encoder source changed; review its identity before use.')
    controls=WORKSPACE/'outputs/kepco_hr_full_eval_960_20261102/indexes'
    target=REPO/'.demo-logs/hr-quality-closeout/encoder'
    target.mkdir(parents=True,exist_ok=True)
    for name in ['cpu_reference.json','cpu_reference.npy']:
        shutil.copy2(controls/name,target/name)
    spec=importlib.util.spec_from_file_location('klink_verified_kepco_encoder',old)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.INDEX=target
    encoder=module.VerifiedLayerEncoder(resident=24,long_microbatch=1,short_microbatch=2)
    sys.path.insert(0,str(REPO))
    from server.hr_evidence import PRIVATE
    app_id='klink-kepco-query-encoder-20261107'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,status,value):
            data=json.dumps(value).encode()
            self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            self.send(200 if self.path=='/health' else 404,dict(app_id=app_id,ready=True,**encoder.runtime) if self.path=='/health' else dict(error='NOT_FOUND'))
        def do_POST(self):
            if self.path!='/embed':return self.send(404,dict(error='NOT_FOUND'))
            if self.headers.get('Origin'):return self.send(403,dict(error='SERVER_REQUESTS_ONLY'))
            try:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=12000:raise ValueError('REQUEST_LIMIT')
                data=json.loads(self.rfile.read(length));text=data.get('text')
                if not isinstance(text,str) or not 2<=len(text)<=500 or PRIVATE.search(text):raise ValueError('GENERAL_QUERY_ONLY')
                started=time.monotonic();values=encoder.encode([text])
                self.send(200,dict(app_id=app_id,model=module.MODEL,revision=module.REVISION,weights_sha256=module.WEIGHTS,
                    dimension=1024,vector=values[0].tolist(),elapsed_ms=round((time.monotonic()-started)*1000,2)))
            except Exception:
                self.send(400,dict(error='QUERY_ENCODING_FAILED'))
    (target/'process.json').write_text(json.dumps(dict(port=args.port,app_id=app_id)),encoding='utf-8')
    print(json.dumps(dict(app_id=app_id,ready=True,port=args.port,source_code_sha256=hashlib.sha256(old.read_bytes()).hexdigest())),flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()


if __name__=='__main__':main()
