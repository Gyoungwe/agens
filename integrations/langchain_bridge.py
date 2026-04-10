import asyncio
from typing import Any, Dict, List

import httpx


def _normalize_text(raw: str, max_chars: int = 800) -> str:
    txt = (raw or "").strip()
    if len(txt) > max_chars:
        return txt[:max_chars] + "..."
    return txt


def _langchain_duckduckgo_search(query: str) -> List[Dict[str, Any]]:
    from langchain_community.tools import DuckDuckGoSearchRun

    tool = DuckDuckGoSearchRun()
    data = tool.run(query)
    return [
        {
            "title": "DuckDuckGo",
            "snippet": _normalize_text(str(data)),
            "source": "langchain_duckduckgo",
        }
    ]


async def _fallback_instant_api(query: str, top_k: int) -> List[Dict[str, Any]]:
    url = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_redirect": 1,
        "no_html": 1,
        "skip_disambig": 0,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    results: List[Dict[str, Any]] = []
    abstract = _normalize_text(data.get("AbstractText", ""))
    if abstract:
        results.append(
            {
                "title": data.get("Heading") or "DuckDuckGo Abstract",
                "snippet": abstract,
                "url": data.get("AbstractURL", ""),
                "source": "duckduckgo_instant_api",
            }
        )

    for item in data.get("RelatedTopics", []):
        if isinstance(item, dict) and item.get("Text"):
            results.append(
                {
                    "title": item.get("FirstURL", "").split("/")[-1] or "Related",
                    "snippet": _normalize_text(item.get("Text", "")),
                    "url": item.get("FirstURL", ""),
                    "source": "duckduckgo_instant_api",
                }
            )
        if len(results) >= top_k:
            break

    return results[:top_k]


async def run_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    query = (query or "").strip()
    if not query:
        return {"success": False, "results": [], "error": "query is required"}

    try:
        results = await asyncio.to_thread(_langchain_duckduckgo_search, query)
        return {
            "success": True,
            "query": query,
            "results": results[:max_results],
            "provider": "langchain_community",
        }
    except Exception:
        fallback_results = await _fallback_instant_api(query, max_results)
        return {
            "success": True,
            "query": query,
            "results": fallback_results,
            "provider": "duckduckgo_fallback",
        }
