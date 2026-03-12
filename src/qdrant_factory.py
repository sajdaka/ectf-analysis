

import os
from qdrant_client import QdrantClient

_client = None

# spawns a singleton QdrantClient based on QDRANT_MODE.
def get_qdrant_client() -> QdrantClient:

    global _client
    if _client is not None:
        return _client

    mode = os.getenv("QDRANT_MODE", "memory")

    if mode == "memory":
        _client = QdrantClient(location=":memory:")
    elif mode == "local":
        _client = QdrantClient(path="./.qdrant_data")
    elif mode == "cloud":
        url = os.getenv("QDRANT_URL")
        api_key = os.getenv("QDRANT_API_KEY")
        if not url or not api_key:
            raise ValueError("QDRANT_MODE=cloud requires QDRANT_URL and QDRANT_API_KEY")
        _client = QdrantClient(url=url, api_key=api_key)
    else:
        raise ValueError(f"Unknown QDRANT_MODE: {mode!r}. Use memory|local|cloud.")

    return _client


def reset_client():
    global _client
    _client = None
