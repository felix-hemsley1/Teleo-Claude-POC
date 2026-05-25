"""Thin wrappers around Anthropic Claude and Voyage AI.

Designed to import cleanly even without API keys so the rest of the system can
be exercised in environments where keys are absent. Calls that actually hit the
network raise a clear error if keys are missing.
"""
import json
import re
from typing import Optional

from shared import config

try:
    from anthropic import Anthropic
except Exception:  # pragma: no cover - anthropic always installed in practice
    Anthropic = None

try:
    import voyageai
except Exception:  # pragma: no cover
    voyageai = None


# Module-level client. Instantiated with whatever key is present (or a
# placeholder) so `import shared.llm` never fails on a missing key.
claude_client = (
    Anthropic(api_key=config.ANTHROPIC_API_KEY or "missing-key")
    if Anthropic is not None
    else None
)

_voyage_client = None


def _get_voyage():
    global _voyage_client
    if _voyage_client is None and voyageai is not None and config.has_voyage():
        _voyage_client = voyageai.Client(api_key=config.VOYAGE_API_KEY)
    return _voyage_client


def claude_complete(
    prompt: str,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    system: Optional[str] = None,
) -> str:
    """Single-turn completion. Returns the text of the first content block."""
    if not config.has_anthropic():
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env to call Claude."
        )
    if claude_client is None:
        raise RuntimeError("anthropic SDK is not installed.")

    model = model or config.CLAUDE_HAIKU_MODEL
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    resp = claude_client.messages.create(**kwargs)
    return "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()


def extract_json(text: str):
    """Parse JSON from a model response, tolerating fences and preamble.

    Falls back to extracting the first balanced JSON array/object substring.
    """
    cleaned = _strip_code_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find first '[' or '{' and matching close.
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start = cleaned.find(open_ch)
        end = cleaned.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Could not parse JSON from model output:\n{text[:500]}")


def claude_json(
    prompt: str,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    system: Optional[str] = None,
):
    """Completion that returns parsed JSON, with one self-repair retry."""
    raw = claude_complete(prompt, model=model, max_tokens=max_tokens, system=system)
    try:
        return extract_json(raw)
    except ValueError:
        repair = (
            "The following text was supposed to be valid JSON but failed to "
            "parse. Return ONLY corrected, valid JSON with no preamble:\n\n"
            f"{raw}"
        )
        fixed = claude_complete(repair, model=model, max_tokens=max_tokens)
        return extract_json(fixed)


def embed(texts: list[str]) -> list[list[float]]:
    """Embed texts with Voyage. Returns list of vectors."""
    client = _get_voyage()
    if client is None:
        raise RuntimeError(
            "VOYAGE_API_KEY is not set (or voyageai not installed)."
        )
    result = client.embed(texts, model=config.VOYAGE_EMBED_MODEL)
    return result.embeddings
