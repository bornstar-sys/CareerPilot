"""Document indexing and scoped retrieval, independent of agent/profile memory."""

from careerpilot.documents import TextDocument
from careerpilot.embeddings import LocalEmbedder, MAX_CHUNKS_PER_CALL
from careerpilot.vector_store import PostgresVectorStore, SearchHit, prepare_document_chunks


class RetrievalService:
    def __init__(self, store: PostgresVectorStore, embedder: LocalEmbedder):
        self.store = store
        self.embedder = embedder

    def index_document(self, owner_id: str, document: TextDocument,
                       *, chunk_size: int = 1000, overlap: int = 150) -> int:
        chunks = prepare_document_chunks(document, chunk_size=chunk_size, overlap=overlap)
        embedded = []
        for start in range(0, len(chunks), MAX_CHUNKS_PER_CALL):
            embedded.extend(self.embedder.embed_chunks(chunks[start:start + MAX_CHUNKS_PER_CALL]))
        # No database writes occur until every embedding has succeeded.
        return self.store.replace_document(owner_id, document, embedded,
                                           chunk_size=chunk_size, overlap=overlap)

    def retrieve(self, owner_id: str, question: str, *, document_ids: list[str],
                 top_k: int = 5, min_similarity: float | None = None) -> list[SearchHit]:
        query = self.embedder.embed_query(question)
        return self.store.search(owner_id, query, document_ids=document_ids,
                                 top_k=top_k, min_similarity=min_similarity)
