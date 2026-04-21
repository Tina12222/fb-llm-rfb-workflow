from __future__ import annotations

import ast
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import List

from httpx import RemoteProtocolError
from langdetect import detect
from openai import APIConnectionError, OpenAI, OpenAIError

SCRIPT_DIR = Path(__file__).resolve().parent

from RAG.rag_core import prompt as pmt

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", ""),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    timeout=600,
    max_retries=0,
)


def query_Gemini(messages, model, stream=True, max_retries=6, backoff=1.0):
    attempt = 0
    while True:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=stream,
                timeout=900,
            )
            break
        except (APIConnectionError, RemoteProtocolError) as exc:
            if attempt >= max_retries:
                raise RuntimeError("Failed to connect after retries.") from exc
            time.sleep(backoff * (2 ** attempt))
            attempt += 1
        except OpenAIError:
            raise

    full_content = []
    try:
        for chunk in resp:
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                text = delta.content if isinstance(delta.content, str) else ""
                if text:
                    print(text, end="", flush=True)
                    full_content.append(text)
    except (RemoteProtocolError, APIConnectionError) as exc:
        if attempt >= max_retries:
            raise RuntimeError("Stream interrupted and retries exhausted.") from exc
        time.sleep(backoff * (2 ** attempt))
        resp_non_stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
            timeout=900,
        )
        content = resp_non_stream.choices[0].message.content or ""
        print(content)
        return content.strip()

    print()
    return "".join(full_content).strip()


def gpt_query(messages, model):
    response = client.chat.completions.create(model=model, messages=messages)
    return response.choices[0].message.content.strip()


def llm_translate(text):
    messages = pmt.template("translate", text=text)
    return gpt_query(messages, model="o4-mini")


def llm_rewrite(query):
    messages = pmt.template("rewrite", query=query)
    return gpt_query(messages, model="o4-mini")


def is_english(text: str) -> bool:
    try:
        return detect(text) == "en"
    except Exception:
        return False


def preprocess_user_query(query: str) -> str:
    translated = query if is_english(query) else llm_translate(query)
    return llm_rewrite(translated)


def _sanitize_list_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9]*\s*|\s*```$", "", s).strip()
    s = unicodedata.normalize("NFKC", s)
    return s


def _parse_keyword_list(raw: str) -> List[str]:
    s = _sanitize_list_text(raw)
    data = None
    try:
        data = ast.literal_eval(s)
    except Exception:
        try:
            data = json.loads(s)
        except Exception:
            items = re.findall(r'["\']([^"\']+)["\']', s)
            if not items:
                items = re.split(r"[\n,;]+", s)
            data = [t.strip() for t in items if t.strip()]

    out: List[str] = []

    def _add(x):
        if x is None:
            return
        if isinstance(x, (list, tuple, set)):
            for y in x:
                _add(y)
            return
        t = str(x).strip()
        if t:
            out.append(t)

    _add(data)
    seen = set()
    dedup = []
    for t in out:
        if t not in seen:
            dedup.append(t)
            seen.add(t)
    return dedup


def get_keywords(query: str) -> List[str]:
    messages = pmt.template("keyword", query=query)
    raw = gpt_query(messages, model="o4-mini")
    return _parse_keyword_list(raw)
