#!/usr/bin/env python3
"""
GitHub Code Search - Search code across GitHub repositories

Usage:
    from search import search_github_code

    results = search_github_code(
        query="authentication",
        language="python",
        max_results=10
    )
"""

import os
import sys
from typing import List, Dict, Optional

try:
    from github import Github
    from github.GithubException import GithubException
except ImportError:
    print("Error: PyGithub not installed. Run: pip install PyGithub")
    sys.exit(1)


class GitHubCodeSearch:
    def __init__(self, token: str = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            print("Warning: No GitHub token found. Rate limit will be lower.")
            self.github = Github()
        else:
            self.github = Github(self.token)

    def search_code(
        self, query: str, language: str = None, max_results: int = 10
    ) -> List[Dict]:
        """
        Search code on GitHub.

        Args:
            query: Search query (supports GitHub search syntax)
            language: Programming language filter (optional)
            max_results: Maximum number of results

        Returns:
            List of search results with file content and metadata
        """
        full_query = query
        if language:
            full_query += f" language:{language}"

        try:
            results = self.github.search_code(
                query=full_query, sort="indexed", order="desc"
            )

            search_results = []
            for item in results.get_page(0)[:max_results]:
                result = {
                    "repository": item.repository.full_name,
                    "file_path": item.path,
                    "url": item.html_url,
                    "sha": item.sha,
                }

                # Try to get file content
                try:
                    file_content = item.repository.get_contents(item.path)
                    if hasattr(file_content, "decoded_content"):
                        result["content"] = file_content.decoded_content.decode(
                            "utf-8", errors="replace"
                        )
                    else:
                        result["content"] = "[Binary file]"
                except Exception:
                    result["content"] = "[Unable to fetch content]"

                search_results.append(result)

            return search_results

        except GithubException as e:
            return [{"error": str(e)}]

    def search_repo(
        self, repo: str, query: str, language: str = None, max_results: int = 10
    ) -> List[Dict]:
        """
        Search code within a specific repository.

        Args:
            repo: Repository in format "owner/repo"
            query: Search query
            language: Programming language filter (optional)
            max_results: Maximum number of results

        Returns:
            List of search results
        """
        full_query = f"repo:{repo} {query}"
        if language:
            full_query += f" language:{language}"

        return self.search_code(query=full_query, max_results=max_results)


def search_github_code(
    query: str, language: str = None, max_results: int = 10, repo: str = None
) -> List[Dict]:
    """
    Search code on GitHub.

    Args:
        query: Search query (e.g., "authentication", "useState")
        language: Programming language (e.g., "python", "javascript", "typescript")
        max_results: Maximum number of results (default: 10)
        repo: Optional specific repository to search (format: "owner/repo")

    Returns:
        List of search results with file content and metadata
    """
    searcher = GitHubCodeSearch()

    if repo:
        return searcher.search_repo(
            repo=repo, query=query, language=language, max_results=max_results
        )
    else:
        return searcher.search_code(
            query=query, language=language, max_results=max_results
        )


def main():
    """CLI interface for testing"""
    if len(sys.argv) < 2:
        print("Usage: python search.py <query> [language] [max_results]")
        print("Example: python search.py 'authentication' python 10")
        sys.exit(1)

    query = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else None
    max_results = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    results = search_github_code(
        query=query, language=language, max_results=max_results
    )

    for i, r in enumerate(results):
        if "error" in r:
            print(f"Error: {r['error']}")
            continue

        print(f"\n{'=' * 60}")
        print(f"[{i + 1}] {r['repository']} - {r['file_path']}")
        print(f"URL: {r['url']}")
        print(f"{'=' * 60}")

        # Show first 30 lines of content
        content_lines = r.get("content", "").split("\n")[:30]
        for j, line in enumerate(content_lines, 1):
            print(f"{j:4d}: {line}")

        if len(r.get("content", "").split("\n")) > 30:
            print(f"\n... (truncated, full content at {r['url']})")


if __name__ == "__main__":
    main()
