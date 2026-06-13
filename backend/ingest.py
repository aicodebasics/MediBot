"""
Document ingestion pipeline.
Parses PDFs/Markdown with Docling, chunks hierarchically, upserts to Qdrant.
Run once: python ingest.py
"""
import os
import uuid
from pathlib import Path
from typing import List, Dict, Any

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    SparseVector,
)
from fastembed import TextEmbedding, SparseTextEmbedding

from config import (
    settings,
    COLLECTION_ACCESS,
    QDRANT_COLLECTION,
    DENSE_MODEL,
    SPARSE_MODEL,
)

DATA_DIR = Path(settings.data_dir)
QDRANT_STORAGE = "./qdrant_storage"

COLLECTION_FILES: Dict[str, List[Path]] = {
    "billing":   list((DATA_DIR / "billing").glob("*")),
    "clinical":  list((DATA_DIR / "clinical").glob("*")),
    "nursing":   list((DATA_DIR / "nursing").glob("*")),
    "equipment": list((DATA_DIR / "equipment").glob("*")),
    "general":   list((DATA_DIR / "general").glob("*")),
}


def get_client() -> QdrantClient:
    if settings.qdrant_url == ":memory:":
        return QdrantClient(path=QDRANT_STORAGE)
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


def setup_collection(client: QdrantClient, dense_dim: int):
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION in existing:
        print(f"Collection '{QDRANT_COLLECTION}' already exists. Delete '{QDRANT_STORAGE}' to re-ingest.")
        return False

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config={"dense": VectorParams(size=dense_dim, distance=Distance.COSINE)},
        sparse_vectors_config={
            "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))
        },
    )
    print(f"Created collection '{QDRANT_COLLECTION}'")
    return True


def chunk_document(file_path: Path, collection: str) -> List[Dict[str, Any]]:
    print(f"  Parsing: {file_path.name}")
    converter = DocumentConverter()
    result = converter.convert(str(file_path))
    doc = result.document

    chunker = HybridChunker()
    chunks = list(chunker.chunk(doc))

    access_roles = COLLECTION_ACCESS[collection]
    records = []

    for chunk in chunks:
        heading = ""
        if hasattr(chunk, "meta") and chunk.meta:
            headings = getattr(chunk.meta, "headings", None)
            if headings:
                heading = headings[-1] if isinstance(headings, list) else str(headings)

        chunk_text = chunk.text.strip()
        if not chunk_text:
            continue

        embedded_text = f"{heading}\n\n{chunk_text}" if heading else chunk_text

        chunk_type = "text"
        if hasattr(chunk, "meta") and chunk.meta:
            label = getattr(chunk.meta, "doc_items", [])
            if label:
                label_type = str(getattr(label[0], "label", "")).lower()
                if "table" in label_type:
                    chunk_type = "table"
                elif "heading" in label_type:
                    chunk_type = "heading"
                elif "code" in label_type:
                    chunk_type = "code"

        records.append({
            "text": embedded_text,
            "metadata": {
                "source_document": file_path.name,
                "collection": collection,
                "access_roles": access_roles,
                "section_title": heading or "—",
                "chunk_type": chunk_type,
            },
        })

    print(f"    → {len(records)} chunks")
    return records


def ingest_all():
    print("Initializing embedding models...")
    dense_model = TextEmbedding(model_name=DENSE_MODEL)
    sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL)

    test_vec = list(dense_model.embed(["test"]))[0]
    dense_dim = len(test_vec)
    print(f"Dense embedding dim: {dense_dim}")

    print(f"Connecting to Qdrant (disk: {QDRANT_STORAGE})...")
    client = get_client()
    created = setup_collection(client, dense_dim)
    if not created:
        return client

    all_records = []
    for collection, files in COLLECTION_FILES.items():
        print(f"\n=== Collection: {collection} ===")
        for file_path in files:
            if file_path.suffix.lower() in {".pdf", ".md", ".txt"}:
                records = chunk_document(file_path, collection)
                all_records.extend(records)

    print(f"\nTotal chunks: {len(all_records)}")
    print("Generating embeddings and upserting to Qdrant...")

    texts = [r["text"] for r in all_records]
    dense_vecs = list(dense_model.embed(texts))
    sparse_vecs = list(sparse_model.embed(texts))

    points = []
    for i, record in enumerate(all_records):
        sv = sparse_vecs[i]
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    "dense": dense_vecs[i].tolist(),
                    "sparse": SparseVector(
                        indices=sv.indices.tolist(),
                        values=sv.values.tolist(),
                    ),
                },
                payload={**record["metadata"], "text": record["text"]},
            )
        )

    batch_size = 64
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(collection_name=QDRANT_COLLECTION, points=batch)
        print(f"  Upserted {min(i + batch_size, len(points))}/{len(points)}")

    print("\nIngestion complete! Qdrant data persisted to disk.")
    return client


if __name__ == "__main__":
    ingest_all()
