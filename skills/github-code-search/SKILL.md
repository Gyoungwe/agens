---
name: github-code-search
description: Search code across GitHub repositories using advanced search queries
version: 0.02
author: OpenCode
---

# GitHub Code Search

Search code across GitHub repositories using the GitHub API with PyGithub library.

## Prerequisites

```bash
pip install PyGithub
```

## Usage

When user asks to search GitHub code, use the `search_github_code` function with:
- `query`: Search query (e.g., "function_name")
- `language`: Optional programming language filter (python, javascript, typescript, etc.)
- `max_results`: Maximum number of results (default: 10)
- `repo`: Optional specific repository to search (format: "owner/repo")

## Examples

```
Search for "authentication" in GitHub code
Find "useState" hook usage across React repositories
Search for "def main" in Python files
Search within a specific repo: repo:facebook/react useState
```

## Authentication

GitHub code search API requires authentication. Set your token:

```bash
export GITHUB_TOKEN="ghp_xxxx"
```

Get a token at: https://github.com/settings/tokens (needs 'repo' scope)

## Features

- Search across all of GitHub or specific repositories
- Filter by language
- View file content and line numbers
- See repository context for each result
- Supports advanced GitHub search syntax
