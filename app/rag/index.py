"""Построение и загрузка поискового индекса.

Индекс = список фрагментов (chunks.json) + их векторы (embeddings.npy).
Векторы считает локальная мультиязычная модель multilingual-e5 (поддерживает
казахский и русский), поэтому платный API для эмбеддингов не нужен.

Сборка индекса:  python -m app.rag.index
"""
import json
import time

import numpy as np

from app import config
from app.rag.chunker import Chunk, chunk_document

_model = None


def get_embedder():
    """Ленивая загрузка модели (≈2 ГБ, грузится один раз при старте)."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(config.EMBED_MODEL, cache_dir=str(config.MODELS_DIR))
    return _model


def _normalize(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def embed_passages(texts: list[str]) -> np.ndarray:
    # e5 обучена с префиксами "passage:" / "query:" — без них качество хуже
    vecs = get_embedder().embed([f"passage: {t}" for t in texts], batch_size=16)
    return _normalize(np.array(list(vecs), dtype=np.float32))


def embed_query(text: str) -> np.ndarray:
    vec = next(iter(get_embedder().embed([f"query: {text}"])))
    return _normalize(np.array(vec, dtype=np.float32))


def chunk_header(c: Chunk | dict) -> str:
    """Заголовок фрагмента: документ + раздел/статья. Добавляется к тексту
    при векторизации, чтобы поиск «понимал», откуда фрагмент."""
    d = c if isinstance(c, dict) else c.to_dict()
    parts = [d["title"]]
    if d.get("section"):
        parts.append(d["section"])
    if d.get("article"):
        word = "Статья" if d["lang"] == "ru" else "бап"
        parts.append(f"{word} {d['article']}" if d["lang"] == "ru" else f"{d['article']}-{word}")
    return ". ".join(parts)


def load_corpus() -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(config.CORPUS_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        chunks.extend(chunk_document(doc))
    return chunks


def build() -> None:
    """Инкрементальная сборка: векторы уже проиндексированных фрагментов (тот же id
    и тот же текст) берутся из старого индекса, модель считает только новые."""
    t0 = time.time()
    chunks = load_corpus()
    print(f"Фрагментов: {len(chunks)} из {len(list(config.CORPUS_DIR.glob('*.json')))} документов")
    texts = [f"{chunk_header(c)}\n{c.text}" for c in chunks]
    cache: dict[tuple[str, str], np.ndarray] = {}
    if (config.INDEX_DIR / "chunks.json").exists():
        old_chunks, old_emb = load()
        cache = {(c["id"], f"{chunk_header(c)}\n{c['text']}"): old_emb[i] for i, c in enumerate(old_chunks)}
    todo = [i for i, c in enumerate(chunks) if (c.id, texts[i]) not in cache]
    print(f"Из кэша: {len(chunks) - len(todo)}, нужно посчитать: {len(todo)}")
    emb = np.zeros((len(chunks), 1024 if not cache else len(next(iter(cache.values())))), dtype=np.float32)
    for i, c in enumerate(chunks):
        if (c.id, texts[i]) in cache:
            emb[i] = cache[(c.id, texts[i])]
    if todo:
        new = embed_passages([texts[i] for i in todo])
        if emb.shape[1] != new.shape[1]:
            emb = np.zeros((len(chunks), new.shape[1]), dtype=np.float32)
        emb[todo] = new
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(config.INDEX_DIR / "embeddings.npy", emb)
    (config.INDEX_DIR / "chunks.json").write_text(
        json.dumps([c.to_dict() for c in chunks], ensure_ascii=False), encoding="utf-8"
    )
    print(f"Индекс сохранён в {config.INDEX_DIR} за {time.time() - t0:.0f} с")


def load() -> tuple[list[dict], np.ndarray]:
    chunks = json.loads((config.INDEX_DIR / "chunks.json").read_text(encoding="utf-8"))
    emb = np.load(config.INDEX_DIR / "embeddings.npy")
    assert len(chunks) == len(emb), "Индекс повреждён: пересоберите (python -m app.rag.index)"
    return chunks, emb


if __name__ == "__main__":
    build()
