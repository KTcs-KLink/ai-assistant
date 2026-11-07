"""CI checks that ONLY the already-experimented local HR subset is importable.

These tests fabricate documents/vectors; they never contact GitHub or Supabase
and never embed, upload, or call a language model.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile

import numpy as np
import pytest

from server.import_lab_to_supabase import (
    EXPECTED_CHUNKS, EXPECTED_DIMENSIONS, HR_SOURCE_IDS, HR_PREFIX,
    MODEL, OLD_PREFIX, REVISION, load_verified,
)

SIZES = {
    "SRC-0001": 203, "SRC-0002": 46, "SRC-0003": 20,
    "SRC-0004": 58, "SRC-0005": 106, "SRC-0006": 76,
    "SRC-0007": 338, "SRC-0008": 716, "SRC-0009": 139,
    "SRC-0010": 26, "SRC-0011": 32, "SRC-0012": 3,
    "SRC-0013": 24, "SRC-0014": 30, "SRC-0015": 15,
    "SRC-0016": 17, "SRC-0017": 13, "SRC-0018": 71,
}


def _fixture_zip(tmp_path, filtered: bool):
    valid = HR_SOURCE_IDS if filtered else set(SIZES)
    sources = [{"source_id": name, "title": name} for name in sorted(valid)]
    chunks = [
        {"chunk_id": f"{source}-c{i:04d}", "source_id": source, "text": f"{source} paragraph {i}"}
        for source, size in SIZES.items() if source in valid for i in range(size)
    ]
    n = len(chunks)
    assert n == (1722 if filtered else 1933)
    # Distinguishable normalized vectors make index alignment testable.
    angles = np.arange(n, dtype=np.float32) / 500
    vectors = np.zeros((n, EXPECTED_DIMENSIONS), dtype=np.float32)
    vectors[:, 0] = np.cos(angles)
    vectors[:, 1] = np.sin(angles)
    variants = {}
    for key in ["body", "path"]:
        stream = io.BytesIO()
        np.save(stream, vectors, allow_pickle=False)
        variants[key] = stream.getvalue()
    blob = "".join(json.dumps(c) + "\n" for c in chunks).encode()
    def done(key):
        return json.dumps({
            "model": MODEL, "revision": REVISION, "pooling": "CLS",
            "max_tokens": 768, "chunks_sha256": hashlib.sha256(blob).hexdigest(),
            "vectors_sha256": hashlib.sha256(variants[key]).hexdigest(),
        }).encode()
    prefix = HR_PREFIX if filtered else OLD_PREFIX
    archive = tmp_path / ("local-only.zip" if filtered else "mixed-original.zip")
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(prefix + "chunks.jsonl", blob)
        z.writestr(prefix + "source_manifest.json", json.dumps(sources))
        for key in ["body", "path"]:
            z.writestr(prefix + f"embeddings_{key}.npy", variants[key])
            z.writestr(prefix + f"embeddings_{key}.done.json", done(key))
    return archive, chunks, vectors


@pytest.mark.parametrize("filtered", [False, True])
def test_allowlist_filters_local_archive_without_reembedding(tmp_path, filtered):
    archive, original, vectors = _fixture_zip(tmp_path, filtered)
    sources, chunks, body, path = load_verified(archive)
    assert len(sources) == 10 and len(chunks) == EXPECTED_CHUNKS
    assert {s["source_id"] for s in sources} == HR_SOURCE_IDS
    assert {c["source_id"] for c in chunks} == HR_SOURCE_IDS
    assert body.shape == path.shape == (EXPECTED_CHUNKS, EXPECTED_DIMENSIONS)
    selected_indices = [i for i, c in enumerate(original) if c["source_id"] in HR_SOURCE_IDS]
    assert np.array_equal(body, vectors[selected_indices])
    assert np.array_equal(path, vectors[selected_indices])


def test_refuse_modified_checksum(tmp_path):
    archive, _, _ = _fixture_zip(tmp_path, True)
    with zipfile.ZipFile(archive, "a") as z:
        z.writestr(HR_PREFIX + "embeddings_body.done.json", json.dumps({
            "model": MODEL, "revision": REVISION, "pooling": "CLS",
            "max_tokens": 768, "chunks_sha256": "0" * 64,
            "vectors_sha256": "0" * 64,
        }))
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_verified(archive)
