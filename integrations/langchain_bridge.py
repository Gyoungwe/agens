import asyncio
import re
from typing import Any, Dict, List
from urllib.parse import quote

import httpx


USER_AGENT = "AgensMultiAgent/1.0 (Multi-Agent Research System)"


def _normalize_text(raw: str, max_chars: int = 800) -> str:
    txt = (raw or "").strip()
    if len(txt) > max_chars:
        return txt[:max_chars] + "..."
    return txt


def _langchain_duckduckgo_search(query: str) -> List[Dict[str, Any]]:
    try:
        from langchain_community.tools import DuckDuckGoSearchRun

        tool = DuckDuckGoSearchRun()
        data = tool.run(query)
        snippet = _normalize_text(str(data))
        if not snippet:
            return []
        return [
            {
                "title": "DuckDuckGo",
                "snippet": snippet,
                "source": "langchain_duckduckgo",
            }
        ]
    except Exception:
        return []


def _query_variants(query: str) -> List[str]:
    q = (query or "").strip()
    variants = [q]

    cleaned = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", q)
    cleaned = " ".join(cleaned.split()).strip()
    if cleaned and cleaned != q:
        variants.append(cleaned)

    lowered = q.lower()
    replacements = {
        "天气": "weather",
        "北京": "Beijing",
        "上海": "Shanghai",
        "深圳": "Shenzhen",
        "广州": "Guangzhou",
        "今天": "today",
        "怎么样": "",
        "如何": "",
        "？": "",
        "?": "",
    }

    translated = q
    for src, dst in replacements.items():
        translated = translated.replace(src, dst)
    translated = " ".join(translated.split()).strip()

    if translated and translated != q and translated.lower() != lowered:
        variants.append(translated)

    lowered_clean = cleaned.lower()
    if "capital of" in lowered_clean:
        variants.append(
            lowered_clean.replace("what is the", "").replace("capital of", "").strip()
        )
        variants.append(lowered_clean.replace("what is the", "").strip())

    if "weather" in lowered_clean and "today" not in lowered_clean:
        variants.append(f"{cleaned} today".strip())

    deduped: List[str] = []
    for variant in variants:
        if variant and variant not in deduped:
            deduped.append(variant)
    return deduped


async def _search_wikipedia(query: str, top_k: int) -> List[Dict[str, Any]]:
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for variant in _query_variants(query):
                search_url = (
                    "https://en.wikipedia.org/w/api.php"
                    f"?action=opensearch&search={quote(variant, safe='')}&limit={top_k}&format=json"
                )
                resp = await client.get(search_url, headers=headers)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                if not isinstance(data, list) or len(data) < 4:
                    continue

                titles = data[1] if len(data) > 1 else []
                urls = data[3] if len(data) > 3 else []
                if not titles:
                    continue

                results = []
                for i, title in enumerate(titles[:top_k]):
                    summary_url = (
                        "https://en.wikipedia.org/api/rest_v1/page/summary/"
                        f"{quote(title, safe='')}"
                    )
                    try:
                        summary_resp = await client.get(summary_url, headers=headers)
                        if summary_resp.status_code == 200:
                            summary_data = summary_resp.json()
                            snippet = _normalize_text(
                                summary_data.get("extract", ""), 300
                            )
                        else:
                            snippet = ""
                    except Exception:
                        snippet = ""

                    results.append(
                        {
                            "title": title,
                            "snippet": snippet,
                            "url": urls[i] if i < len(urls) else "",
                            "source": "wikipedia",
                        }
                    )

                if results:
                    return results
    except Exception:
        return []

    return []


async def _fallback_instant_api(query: str, top_k: int) -> List[Dict[str, Any]]:
    url = "https://api.duckduckgo.com/"

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            for variant in _query_variants(query):
                params = {
                    "q": variant,
                    "format": "json",
                    "no_redirect": 1,
                    "no_html": 1,
                    "skip_disambig": 0,
                }
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    continue

                try:
                    data = resp.json()
                except Exception:
                    continue

                results: List[Dict[str, Any]] = []
                abstract = _normalize_text(data.get("AbstractText", ""))
                if abstract:
                    results.append(
                        {
                            "title": data.get("Heading") or "DuckDuckGo",
                            "snippet": abstract,
                            "url": data.get("AbstractURL", ""),
                            "source": "duckduckgo_instant",
                        }
                    )

                for item in data.get("RelatedTopics", []):
                    if isinstance(item, dict) and item.get("Text"):
                        results.append(
                            {
                                "title": item.get("FirstURL", "").split("/")[-1]
                                or "Related",
                                "snippet": _normalize_text(item.get("Text", "")),
                                "url": item.get("FirstURL", ""),
                                "source": "duckduckgo_instant",
                            }
                        )
                    if len(results) >= top_k:
                        break

                if results:
                    return results[:top_k]
    except Exception:
        return []

    return []


async def run_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    query = (query or "").strip()
    if not query:
        return {"success": False, "results": [], "error": "query is required"}

    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_langchain_duckduckgo_search, query), timeout=5.0
        )
        if results and results[0].get("snippet"):
            return {
                "success": True,
                "query": query,
                "results": results[:max_results],
                "provider": "langchain_community",
            }
    except (asyncio.TimeoutError, Exception):
        pass

    wiki_results = await _search_wikipedia(query, max_results)
    if wiki_results:
        return {
            "success": True,
            "query": query,
            "results": wiki_results,
            "provider": "wikipedia",
        }

    fallback_results = await _fallback_instant_api(query, max_results)
    return {
        "success": True,
        "query": query,
        "results": fallback_results,
        "provider": "duckduckgo_fallback",
    }
