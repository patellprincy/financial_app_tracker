from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_classification_prompt_template() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "classify_prompt.txt"
    return prompt_path.read_text(encoding="utf-8")
