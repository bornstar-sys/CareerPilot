"""Index two illustrative sources, then retrieve a traceable Android passage.

Run a second time with --query-only to read previously stored vectors from a
new Python process. No Groq call or profile-memory write is made.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from careerpilot.database import load_database_settings
from careerpilot.documents import TextDocument
from careerpilot.embeddings import LocalEmbedder
from careerpilot.retrieval import RetrievalService
from careerpilot.vector_store import PostgresVectorStore


OWNER = 'phase4-retrieval-demo'
DOCUMENTS = [
    TextDocument('demo-android-storage', 'illustrative_android_storage.txt',
        'Illustrative Android study notes, not a live job listing.\n'
        'Use the Room persistence library to store Android application data offline. '
        'Room stores structured records in a local SQLite database. '
        'Use entities, DAO interfaces, and a database class to read and write notes. '
        'Synchronize local notes with a server using REST APIs when connectivity returns.'),
    TextDocument('demo-web-styling', 'illustrative_web_styling.txt',
        'Illustrative web design study notes, not a live job listing.\n'
        'Use CSS to style a website. Flexbox and Grid arrange page elements. '
        'Media queries adapt layouts to screen sizes. Choose readable fonts and '
        'sufficient color contrast. Use semantic HTML for accessible page structure.'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db-env', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'infra/postgres/.env')
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--allow-download', action='store_true')
    parser.add_argument('--query-only', action='store_true')
    args = parser.parse_args()

    store = PostgresVectorStore(load_database_settings(args.db_env))
    store.initialize()
    service = RetrievalService(store, LocalEmbedder(cache_dir=args.cache_dir,
                                local_files_only=not args.allow_download))
    if not args.query_only:
        for document in DOCUMENTS:
            service.index_document(OWNER, document, chunk_size=700, overlap=100)
    ids = [d.document_id for d in DOCUMENTS]
    listed = {d.document_id: d for d in store.list_documents(OWNER)}
    if any(d.document_id not in listed or
           listed[d.document_id].content_sha256 != d.content_sha256 for d in DOCUMENTS):
        raise SystemExit('Demo sources are missing or changed. Run without --query-only first.')
    question = 'How can I store Android application data offline?'
    hits = service.retrieve(OWNER, question, document_ids=ids, top_k=2)
    if len(hits) != 2 or hits[0].chunk.document_id != 'demo-android-storage':
        raise RuntimeError('Expected the Android storage source to rank first.')
    for hit in hits:
        source = next(d for d in DOCUMENTS if d.document_id == hit.chunk.document_id)
        if source.text[hit.chunk.start_char:hit.chunk.end_char] != hit.chunk.text:
            raise RuntimeError('Retrieved source offsets do not match the original text.')
    scoped = service.retrieve(OWNER, question, document_ids=['demo-web-styling'])
    if len(scoped) != 1 or scoped[0].chunk.document_id != 'demo-web-styling':
        raise RuntimeError('Document filtering failed.')
    if service.retrieve(OWNER + '-empty', question, document_ids=ids):
        raise RuntimeError('Owner filtering failed.')
    print(json.dumps({
        'check': 'PASS',
        'mode': 'query-only' if args.query_only else 'index-and-query',
        'stored_documents': len(listed),
        'stored_chunks': sum(d.chunk_count for d in listed.values()),
        'question': question,
        'owner_filter': 'PASS', 'document_filter': 'PASS', 'source_offsets': 'PASS',
        'hits': [dict(similarity=round(h.similarity, 6), **asdict(h.chunk)) for h in hits],
    }, indent=2, ensure_ascii=True))


if __name__ == '__main__':
    main()
