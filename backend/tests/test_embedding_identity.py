import shutil

import pytest

from careerpilot import embeddings
from careerpilot.embeddings import EmbeddingError, LocalEmbedder, fingerprint_model


@pytest.fixture
def model_files(tmp_path, monkeypatch):
    root = tmp_path / 'first'
    root.mkdir()
    for name in ('model_optimized.onnx', 'tokenizer.json', 'tokenizer_config.json'):
        (root / name).write_bytes(name.encode())
    monkeypatch.setattr(embeddings, 'version', lambda name: 'test-v1')
    return root


def test_identity_does_not_depend_on_cache_location(model_files):
    other = model_files.parent / 'second'
    shutil.copytree(model_files, other)
    assert fingerprint_model(model_files) == fingerprint_model(other)


@pytest.mark.parametrize('name', ['model_optimized.onnx', 'tokenizer.json', 'tokenizer_config.json',
                                 'config.json', 'special_tokens_map.json'])
def test_model_or_tokenizer_change_changes_identity(model_files, name):
    before = fingerprint_model(model_files)
    (model_files / name).write_bytes(b'changed')
    assert fingerprint_model(model_files) != before


def test_runtime_and_preprocessing_change_identity(model_files, monkeypatch):
    before = fingerprint_model(model_files)
    monkeypatch.setattr(embeddings, 'version', lambda name: 'test-v2')
    assert fingerprint_model(model_files) != before
    second = fingerprint_model(model_files)
    monkeypatch.setattr(embeddings, 'QUERY_PREFIX', 'new instruction: ')
    assert fingerprint_model(model_files) != second


def test_missing_model_is_rejected(model_files):
    (model_files / 'model_optimized.onnx').unlink()
    with pytest.raises(EmbeddingError):
        fingerprint_model(model_files)


def test_backend_identity_attaches_to_vectors():
    class Backend:
        max_tokens = 512
        space_id = 'a' * 64
        def count_tokens(self, text):
            return 5
        def embed(self, texts):
            return [(2.0,) + (0.0,) * 383 for _ in texts]
    vector = LocalEmbedder(backend=Backend()).embed_query('offline storage')
    assert vector.space_id == 'a' * 64
    assert vector.values[0] == 1.0
