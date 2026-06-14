"""LLM provider adapters for the copilot's optional LLM mode.

An adapter is a simple ``callable(prompt: str) -> str`` (the shape the copilot
expects): it sends the prompt to the model and returns the model's text, which the
copilot parses as JSON (``{"tool",...}`` | ``{"final",...}``). The copilot's guard
is the backstop — even a misbehaving model cannot introduce a number that isn't in
a tool Result.

Gemini is the first provider. The API key is read from the environment
(``GEMINI_API_KEY``); it is never logged or written to disk.
"""
from __future__ import annotations

import json
import os
import time

import requests

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
_TIMEOUT = 60
_RETRIES = 3

_SYSTEM_INSTRUCTION = (
    "You are a tool-using financial planning copilot. Respond with a SINGLE JSON "
    "object and nothing else: either {\"tool\": \"<name>\", \"args\": {...}} to call "
    "a tool, or {\"final\": \"<reply>\"} when done. Never state a dollar amount, "
    "percentage, or age that did not come from a tool result."
)


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        # Blocked or empty — surface a safe final reply rather than crashing.
        fb = data.get("promptFeedback", {})
        reason = fb.get("blockReason") or "no candidates returned"
        return json.dumps({"final": f"I couldn't produce a response ({reason}). "
                                    "Please rephrase or use the guided form."})
    parts = (candidates[0].get("content", {}) or {}).get("parts", []) or []
    text = "".join(p.get("text", "") for p in parts).strip()
    return text or json.dumps({"final": "I couldn't produce a response."})


def make_gemini(api_key: str | None = None, model: str | None = None,
                timeout: int = _TIMEOUT, retries: int = _RETRIES):
    """Return a ``callable(prompt)->str`` backed by Gemini ``generateContent``."""
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    model = model or DEFAULT_GEMINI_MODEL
    url = f"{GEMINI_BASE}/{model}:generateContent"

    def _call(prompt: str) -> str:
        body = {
            "system_instruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        # Newer keys (AQ.* / OAuth) use Bearer; classic AIza* use x-goog-api-key.
        # Try the api-key header first, then fall back to Bearer on auth failure.
        header_variants = [{"x-goog-api-key": key}, {"Authorization": f"Bearer {key}"}]
        delay, last = 2, None
        for attempt in range(1, retries + 1):
            headers = header_variants[min(attempt - 1, 1)]
            headers = {**headers, "Content-Type": "application/json"}
            try:
                r = requests.post(url, headers=headers, json=body, timeout=timeout)
                if r.status_code == 200:
                    return _extract_text(r.json())
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code in (401, 403) and attempt < retries:
                    continue  # try the other auth scheme
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(delay); delay *= 2; continue
                raise RuntimeError(f"Gemini error: {last}")
            except requests.RequestException as e:
                last = f"network error: {e}"
                time.sleep(delay); delay *= 2
        raise RuntimeError(f"Gemini call failed after {retries} attempts: {last}")

    return _call


def get_default_llm():
    """Return a configured LLM callable if a provider key is present, else None.
    Lets the web/CLI opt into LLM mode automatically without hard-failing."""
    if os.environ.get("GEMINI_API_KEY"):
        return make_gemini()
    return None
