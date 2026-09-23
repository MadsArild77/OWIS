"""Cached OpenAI embeddings. Similarity proposes candidates, never proves identity."""
import hashlib
import json
import math
import httpx
from owis.core.config import settings
from owis.core.storage.db import get_conn

VERSION = "news-match-v2"

def article_text(item):
    return (str(item.get("title") or "")[:500] + "\n" +
            str(item.get("cleaned_text") or item.get("summary") or "")[:5000])

def cache_key(kind, payload):
    data = json.dumps([VERSION, kind, settings.AI_BASE_URL, settings.AI_MODEL,
                       settings.AI_EMBEDDING_MODEL, settings.AI_INPUT_MAX_CHARS, payload], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()

def read_cache(key):
    with get_conn() as conn:
        row = conn.execute("SELECT value_json FROM news_ai_cache WHERE cache_key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else None

def write_cache(key, value):
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO news_ai_cache VALUES (?, ?)", (key, json.dumps(value)))

def cosine(a, b):
    if not a or len(a) != len(b): return 0.0
    denom = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b)) / denom if denom else 0.0

def embed_articles(items):
    vectors, missing = {}, []
    for item in items:
        text = article_text(item)
        key = cache_key("embedding", text)
        value = read_cache(key)
        if value is not None: vectors[int(item["id"])] = value
        else: missing.append((item, text, key))
    if missing and not (settings.AI_ENABLED and settings.AI_API_KEY):
        raise RuntimeError("OpenAI matching requires OWI_AI_ENABLED=true and OPENAI_API_KEY in the server environment.")
    with httpx.Client(timeout=30) as client:
        for start in range(0, len(missing), 32):
            batch = missing[start:start+32]
            response = client.post(settings.AI_BASE_URL.rstrip("/") + "/embeddings",
                headers={"Authorization": "Bearer " + settings.AI_API_KEY},
                json={"model": settings.AI_EMBEDDING_MODEL, "input": [row[1] for row in batch]})
            response.raise_for_status()
            rows = sorted(response.json()["data"], key=lambda row: row["index"])
            if [row["index"] for row in rows] != list(range(len(batch))):
                raise ValueError("Incomplete embedding response")
            for (item, text, key), row in zip(batch, rows):
                vector = row["embedding"]
                if not vector or not all(isinstance(x, (int,float)) and math.isfinite(x) for x in vector):
                    raise ValueError("Invalid embedding vector")
                vectors[int(item["id"])] = vector
                write_cache(key, vector)
    return vectors
