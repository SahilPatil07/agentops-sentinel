import hashlib
import math
import re

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{1,}")


class HashingEmbedder:
    """Deterministic token hashing for an offline retrieval baseline."""

    def __init__(self, dimensions: int = 384) -> None:
        if not 64 <= dimensions <= 2048:
            raise ValueError("Embedding dimensions must be between 64 and 2048")
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = TOKEN_PATTERN.findall(text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude:
            return [value / magnitude for value in vector]
        return vector
