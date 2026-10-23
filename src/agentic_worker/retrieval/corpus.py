import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from agentic_worker.retrieval.models import DocumentMetadata, KnowledgeDocument

Filename = Annotated[
    str, StringConstraints(min_length=3, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*\.md$")
]


class ManifestEntry(DocumentMetadata):
    filename: Filename


class CorpusManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    version: Annotated[str, StringConstraints(min_length=1, max_length=50)]
    documents: list[ManifestEntry] = Field(min_length=1, max_length=100)


def load_corpus(path: Path) -> tuple[str, list[KnowledgeDocument]]:
    manifest_path = path / "manifest.json"
    manifest = CorpusManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if len({entry.document_id for entry in manifest.documents}) != len(manifest.documents):
        raise ValueError("Duplicate document IDs in corpus manifest")
    if len({entry.filename for entry in manifest.documents}) != len(manifest.documents):
        raise ValueError("Duplicate filenames in corpus manifest")
    documents = []
    for entry in manifest.documents:
        content = (path / entry.filename).read_text(encoding="utf-8")
        documents.append(
            KnowledgeDocument(**entry.model_dump(exclude={"filename"}), content=content)
        )
    return manifest.version, documents


def corpus_summary(path: Path) -> str:
    version, documents = load_corpus(path)
    return json.dumps({"version": version, "documents": len(documents)})
