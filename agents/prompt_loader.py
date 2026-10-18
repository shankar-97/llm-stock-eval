from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name_and_version: str) -> str:
    """name_and_version e.g. 'fundamentals@v1' -> prompts/fundamentals@v1.md"""
    return (PROMPTS_DIR / f"{name_and_version}.md").read_text()
