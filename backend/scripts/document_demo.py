"""Run from backend: python scripts/document_demo.py [optional .txt/.md path]."""

import argparse
from dataclasses import asdict
import json

from careerpilot.documents import TextDocument, chunk_document, load_text_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?")
    parser.add_argument("--document-id", default="demo-android-role")
    args = parser.parse_args()
    if args.path:
        document = load_text_document(args.path, document_id=args.document_id)
    else:
        document = TextDocument(
            document_id=args.document_id,
            source_name="example_android_role.txt",
            text=(
                "Illustrative Android role, not a live job listing.\n"
                "Required skills: Kotlin, Jetpack Compose, Room, and REST APIs.\n"
                "Practice: build an offline notes app and synchronize notes with a server.\n"
                "Use Git to track changes and write tests for the data layer.\n"
            ),
        )
    chunks = chunk_document(document, chunk_size=120, overlap=25)
    print(json.dumps({"document_id": document.document_id,
                      "chunk_count": len(chunks),
                      "chunks": [asdict(chunk) for chunk in chunks]}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
