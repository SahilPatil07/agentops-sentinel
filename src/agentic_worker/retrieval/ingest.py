import argparse
from pathlib import Path

from agentic_worker.config import Settings
from agentic_worker.retrieval.corpus import load_corpus
from agentic_worker.retrieval.index import KnowledgeIndex


def sync_corpus(index: KnowledgeIndex, corpus_path: Path) -> tuple[str, int, int]:
    version, documents = load_corpus(corpus_path)
    chunks = index.ingest(documents)
    return version, len(documents), chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Index the local AgentOps knowledge corpus")
    parser.add_argument("--knowledge-path")
    parser.add_argument("--vector-store-path")
    arguments = parser.parse_args()
    settings = Settings()
    corpus_path = Path(arguments.knowledge_path or settings.knowledge_path)
    vector_path = arguments.vector_store_path or settings.vector_store_path
    version, documents, chunks = sync_corpus(KnowledgeIndex(vector_path), corpus_path)
    print(f"Indexed corpus {version}: {documents} documents, {chunks} chunks")


if __name__ == "__main__":
    main()
