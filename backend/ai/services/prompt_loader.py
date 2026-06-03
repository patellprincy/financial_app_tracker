from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=1)
def get_classification_prompt_template() -> str:
    return (_PROMPTS_DIR / "classify_prompt.txt").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def get_statement_cleanup_prompt() -> str:
    """
    Static system prompt for statement cleanup.
    Cached in-process — only the instructions are cached here.
    Candidate transaction rows are always passed dynamically as the user message.
    """
    return (_PROMPTS_DIR / "statement_cleanup_prompt.txt").read_text(encoding="utf-8")
