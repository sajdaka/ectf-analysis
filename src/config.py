

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


def _int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))



QDRANT_MODE = os.getenv("QDRANT_MODE", "memory")


LITELLM_PROXY_URL = os.getenv("LITELLM_PROXY_URL", "http://localhost:4000")


REPOS_DIR = Path(os.getenv("REPOS_DIR", "./repos"))
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "./reports"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", "./logs"))


MAX_HYPOTHESES_PER_TEAM = _int("MAX_HYPOTHESES_PER_TEAM", 12)
MAX_TOOL_CALLS_PER_HYPOTHESIS = _int("MAX_TOOL_CALLS_PER_HYPOTHESIS", 10)
EVIDENCE_COMPRESS_EVERY = _int("EVIDENCE_COMPRESS_EVERY", 3)


CONFIDENCE_OPUS_THRESHOLD = _float("CONFIDENCE_OPUS_THRESHOLD", 0.75)
MEMORY_DEDUP_THRESHOLD = _float("MEMORY_DEDUP_THRESHOLD", 0.92)
TIER2A_SCORE_THRESHOLD = _float("TIER2A_SCORE_THRESHOLD", 0.85)
TIER2B_SCORE_THRESHOLD = _float("TIER2B_SCORE_THRESHOLD", 0.65)
