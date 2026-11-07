"""Loopback-only, fresh query embeddings using the existing local BGE-M3 checkpoint.

Uses the existing pinned Transformers environment and streams official FP32
layers on CPU. Never downloads, rebuilds document vectors, writes the original
index, persists questions, or reads provider credentials.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import struct
import threading
import time
import uuid

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

MODEL = "BAAI/bge-m3"
REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
WEIGHTS_REVISION = "9a0624b896d81da7492a910ffa53731274b6cf3d"
WEIGHTS_SHA = "993b2248881724788dcab8c644a91dfd63584b6e5604ff2037cb5541e1e38e7e"
TOKENIZER_SHA = "21106b6d7dab2952c1d496fb21d5dc9db75c28ed361a05f5020bbba27810dd08"


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


class QueryEncoder:
    def __init__(self):
        import numpy as np
        import torch
        import transformers
        import tokenizers
        from accelerate import init_empty_weights
        from transformers import AutoConfig, AutoTokenizer
        from transformers.models.xlm_roberta.modeling_xlm_roberta import (
            XLMRobertaEmbeddings, XLMRobertaLayer, create_position_ids_from_input_ids)
        from transformers.modeling_utils import PreTrainedModel
        from types import SimpleNamespace

        if transformers.__version__ != "4.45.2" or tokenizers.__version__ != "0.20.3":
            raise ValueError("CANONICAL_EMBEDDING_BACKEND_REQUIRED")

        self.np, self.torch = np, torch
        torch.set_num_threads(4)
        cache = Path.home() / ".cache/huggingface/hub/models--BAAI--bge-m3/snapshots"
        tokenizer_path, weights_path = cache / REVISION, cache / WEIGHTS_REVISION / "model.safetensors"
        if sha(tokenizer_path / "tokenizer.json") != TOKENIZER_SHA or sha(weights_path) != WEIGHTS_SHA:
            raise ValueError("LOCAL_CHECKPOINT_IDENTITY_MISMATCH")
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
        self.config = AutoConfig.from_pretrained(tokenizer_path, local_files_only=True)
        self.config._attn_implementation = "eager"
        self.position_ids = create_position_ids_from_input_ids
        self.padding_id = self.config.pad_token_id
        self.layer_class, self.empty_weights = XLMRobertaLayer, init_empty_weights
        self.mask_function = lambda attention, shape: PreTrainedModel.get_extended_attention_mask(
            SimpleNamespace(dtype=torch.float32, config=self.config), attention, shape, dtype=torch.float32)
        self.weights_path = weights_path
        with weights_path.open("rb") as file:
            self.header_size = struct.unpack("<Q", file.read(8))[0]
            self.header = json.loads(file.read(self.header_size))
        self.words = self.mapped("embeddings.word_embeddings.weight")
        with init_empty_weights():
            self.embeddings = XLMRobertaEmbeddings(self.config)
        for name, parameter in list(self.embeddings.named_parameters()):
            if name == "word_embeddings.weight":
                continue
            value = self.tensor("embeddings." + name)
            if value.shape != parameter.shape:
                raise ValueError("EMBEDDING_PARAMETER_SHAPE")
            parent, leaf = name.rsplit(".", 1)
            self.embeddings.get_submodule(parent).register_parameter(leaf, torch.nn.Parameter(value, requires_grad=False))
        self.embeddings.eval()
        self.lock = threading.Lock()
        self.identity = dict(model=MODEL, revision=REVISION, weights_sha256=WEIGHTS_SHA,
                             dimension=1024, pooling="CLS_then_FP32_L2", truncation=False,
                             execution="LOCAL_CPU_FP32_OFFICIAL_LAYER_STREAM")
        self.instance = uuid.uuid4().hex
        print("Local CPU BGE-M3 query encoder ready; existing document vectors are unchanged.", flush=True)

    def mapped(self, name):
        info = self.header[name]
        if info["dtype"] != "F32":
            raise ValueError("CHECKPOINT_PARAMETER_DTYPE")
        return self.np.memmap(self.weights_path, mode="r", dtype="<f4",
            offset=8 + self.header_size + info["data_offsets"][0], shape=tuple(info["shape"]))

    def tensor(self, name):
        return self.torch.from_numpy(self.np.array(self.mapped(name), dtype=self.np.float32, copy=True))

    def encode(self, text):
        torch, np = self.torch, self.np
        with self.lock:
            encoded = self.tokenizer([text], padding=True, truncation=False, add_special_tokens=True, return_tensors="pt")
            if int(encoded["attention_mask"].sum()) > 8192:
                raise ValueError("QUERY_TOO_LONG_NOT_TRUNCATED")
            ids = encoded.pop("input_ids")
            positions = self.position_ids(ids, self.padding_id, 0)
            rows = torch.from_numpy(np.array(self.words[ids.numpy()], dtype=np.float32, copy=True))
            mask = self.mask_function(encoded["attention_mask"], ids.shape)
            with torch.no_grad():
                hidden = self.embeddings(inputs_embeds=rows, position_ids=positions, token_type_ids=torch.zeros_like(ids))
                del rows
                for index in range(self.config.num_hidden_layers):
                    with self.empty_weights():
                        layer = self.layer_class(self.config)
                    state = {name: self.tensor(f"encoder.layer.{index}." + name) for name in layer.state_dict()}
                    loaded = layer.load_state_dict(state, strict=True, assign=True)
                    if loaded.missing_keys or loaded.unexpected_keys:
                        raise ValueError("ENCODER_PARAMETER_LOAD")
                    layer.eval()
                    hidden = layer(hidden, attention_mask=mask, output_attentions=False)[0]
                    del layer, state, loaded
                    gc.collect()
                vector = torch.nn.functional.normalize(hidden[:, 0, :], p=2, dim=1).numpy()[0].astype(np.float32)
            del hidden
        if vector.shape != (1024,) or not np.isfinite(vector).all() or abs(float(np.linalg.norm(vector)) - 1) > 2e-4:
            raise ValueError("INVALID_QUERY_EMBEDDING")
        return vector.tolist()


def handler_for(encoder):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send(self, status, value):
            body = json.dumps(value).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != "/health":
                return self.send(404, {"error": "not found"})
            self.send(200, dict(app="KLINK_HR_QUERY_ENCODER", ready=True, **encoder.identity,
                                instance_id=encoder.instance, query_cache_preloaded=False, question_storage=False))

        def do_POST(self):
            if self.path != "/embed":
                return self.send(404, {"error": "not found"})
            if self.headers.get("Origin"):
                return self.send(403, {"error": "server requests only"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16000:
                    raise ValueError("size")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or set(payload) != {"text"}:
                    raise ValueError("shape")
                text = payload["text"]
                # The BFF enforces 500-character questions. Longer original
                # window texts are accepted here only for numeric startup controls.
                if not isinstance(text, str) or not 2 <= len(text.strip()) <= 6000:
                    raise ValueError("text")
                started = time.perf_counter()
                vector = encoder.encode(text)
                self.send(200, dict(**encoder.identity, vector=vector, computed=True, cached=False,
                                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2)))
            except Exception:
                self.send(400, {"error": "query embedding unavailable"})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8832)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("Invalid port")
    encoder = QueryEncoder()
    ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(encoder)).serve_forever()


if __name__ == "__main__":
    main()
