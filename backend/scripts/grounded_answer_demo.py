"""Document Q&A checks: deterministic offline fixtures, or explicit --live.

--live reads the Step 3 demo sources from PostgreSQL, embeds queries locally,
and makes two Groq calls using the existing backend configuration. It does not
index documents or read/write profile memory.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from careerpilot.document_agent import run_document_agent
from careerpilot.documents import TextDocument, chunk_document
from careerpilot.vector_store import SearchHit


OWNER = 'phase4-retrieval-demo'
IDS = ['demo-android-storage', 'demo-web-styling']
QUESTION = 'How can I store Android application data offline?'
UNSUPPORTED = 'What annual salary in INR does the Android employer guarantee?'


class FixtureRetriever:
    def retrieve(self, owner_id, question, *, document_ids, top_k, min_similarity):
        doc = TextDocument(IDS[0], 'offline_fixture.txt',
                           'Use the Room persistence library to store Android application data offline.')
        return [SearchHit(chunk_document(doc)[0], 0.8)]


def fixture_generator(settings, prompt):
    """Scripted test fixture, not a real language model or relevance checker."""
    payload = json.loads(prompt)
    if payload['question'] == QUESTION:
        return json.dumps({'status': 'answered', 'evidence': [
            {'source_id': 'S1', 'quote': payload['passages'][0]['text']} ]})
    return '{"status":"insufficient_evidence","evidence":[]}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--db-env', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'infra/postgres/.env')
    parser.add_argument('--cache-dir', type=Path)
    args = parser.parse_args()
    settings = None
    generator = fixture_generator
    retrieval = FixtureRetriever()
    if args.live:
        from careerpilot.config import load_settings
        from careerpilot.database import load_database_settings
        from careerpilot.embeddings import LocalEmbedder
        from careerpilot.retrieval import RetrievalService
        from careerpilot.vector_store import PostgresVectorStore
        settings = load_settings(
            env_file=Path(__file__).resolve().parents[1] / ".env"
        )
        store = PostgresVectorStore(load_database_settings(args.db_env))
        if not set(IDS).issubset({d.document_id for d in store.list_documents(OWNER)}):
            raise SystemExit('Run scripts/retrieval_demo.py first to store the Step 3 demo documents.')
        retrieval = RetrievalService(store, LocalEmbedder(cache_dir=args.cache_dir))
        generator = None
    results = []
    for question, scope in ((QUESTION, IDS), (UNSUPPORTED, IDS), (QUESTION, [])):
        results.append(run_document_agent(settings, question, retrieval_service=retrieval,
                                          owner_id=OWNER, document_ids=scope, generator=generator))
    positive, unsupported, empty = results
    checks = {
        'cited_answer': positive.status == 'answered' and bool(positive.citations)
                        and any('Room' in c.quote for c in positive.citations),
        'unsupported_question': unsupported.status == 'insufficient_evidence'
                                and unsupported.reason == 'model_insufficient_evidence',
        'empty_scope_without_model': empty.reason == 'no_selected_documents' and not empty.model_called,
    }
    print(json.dumps({'check': 'PASS' if all(checks.values()) else 'FAIL',
        'mode': 'live-postgres-and-groq' if args.live else 'offline-scripted-fixtures',
        'checks': checks,
        'results': [asdict(r) for r in results]}, indent=2, ensure_ascii=True))
    if not all(checks.values()):
        raise SystemExit('A document-Q&A check failed. Share the output before proceeding.')


if __name__ == '__main__':
    main()
