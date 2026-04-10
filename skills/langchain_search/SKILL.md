---
skill_id: langchain_search
name: LangChain Web Search
description: Search web knowledge via LangChain DuckDuckGo tool with fallback.
version: 0.02
author: system
tags: [langchain, search, web]
tools: []
permissions:
  network: true
  filesystem: false
  shell: false
agents: [research_agent, orchestrator]
enabled: true
source: local
---

# LangChain Web Search

Use LangChain's DuckDuckGo tool when available.
If LangChain community tools are not installed, the skill falls back to DuckDuckGo Instant API.

Input:
- `instruction`: search query
- `context.max_results` (optional): number of results
