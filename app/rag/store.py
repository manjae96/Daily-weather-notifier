"""Qdrant 기반 RAG 저장/조회."""
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from app.config import settings
from app.llm.client import get_client

VECTOR_SIZE = 768  # text-embedding-004

def _client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)

def ensure_collection() -> None:
    c = _client()
    names = [col.name for col in c.get_collections().collections]
    if settings.qdrant_collection not in names:
        c.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qm.VectorParams(size=VECTOR_SIZE, distance=qm.Distance.COSINE),
        )

def _chunk(text: str, size: int = 500) -> list[str]:
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) < size:
            buf += ("\n\n" if buf else "") + p
        else:
            if buf:
                chunks.append(buf)
            buf = p
    if buf:
        chunks.append(buf)
    return chunks

async def ingest_directory(docs_dir: str = "docs/rag") -> int:
    ensure_collection()
    llm = get_client()
    c = _client()
    points, pid = [], 0
    for md in Path(docs_dir).glob("*.md"):
        for chunk in _chunk(md.read_text(encoding="utf-8")):
            vec = (await llm.embed([chunk]))[0]
            points.append(qm.PointStruct(id=pid, vector=vec,
                payload={"source": md.name, "text": chunk}))
            pid += 1
    if points:
        c.upsert(collection_name=settings.qdrant_collection, points=points)
    return len(points)

async def retrieve(query: str, top_k: int = 3) -> list[dict]:
    llm = get_client()
    qvec = (await llm.embed([query]))[0]
    c = _client()
    hits = c.search(collection_name=settings.qdrant_collection, query_vector=qvec, limit=top_k)
    return [{"text": h.payload["text"], "source": h.payload["source"], "score": h.score} for h in hits]
