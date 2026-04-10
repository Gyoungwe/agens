#!/usr/bin/env python3
"""
Agens Multi-Agent System - Comprehensive Test Suite
Tests all API endpoints and features
"""

import requests
import json
import time
import sys
from typing import Dict, Any, List

BASE_URL = "http://localhost:8000"
RESULTS: List[Dict[str, Any]] = []


def print_header(text: str):
    print(f"\n{'=' * 60}")
    print(f" {text}")
    print(f"{'=' * 60}")


def print_result(name: str, success: bool, detail: str = ""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"  {status}: {name}")
    if detail:
        print(f"         {detail}")
    RESULTS.append({"name": name, "success": success, "detail": detail})


def test_health() -> bool:
    """Test health endpoint"""
    print_header("Health Check")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        data = resp.json()
        print(f"  Status: {data.get('status')}")
        print(f"  Provider: {data.get('provider')}")
        print(f"  Model: {data.get('model')}")
        print(f"  Skills: {data.get('skills_count')}")
        print(f"  Memory: {data.get('memory_count')}")
        print_result("Health endpoint", data.get("status") == "healthy")
        return data.get("status") == "healthy"
    except Exception as e:
        print_result("Health endpoint", False, str(e))
        return False


def test_skills_list() -> bool:
    """Test skills list endpoint"""
    print_header("Skills Management")
    try:
        resp = requests.get(f"{BASE_URL}/skills/", timeout=5)
        data = resp.json()
        skills = data.get("skills", [])
        print(f"  Total skills: {len(skills)}")
        for s in skills:
            print(f"    - {s['skill_id']} ({s.get('source', 'unknown')})")
        print_result("List skills", len(skills) >= 0)
        return True
    except Exception as e:
        print_result("List skills", False, str(e))
        return False


def test_skill_import() -> bool:
    """Test Claude skill import"""
    print_header("Skill Import")
    try:
        schema = {
            "name": "test_calculator",
            "description": "A test calculator skill",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression"}
                },
                "required": ["expression"],
            },
        }

        # Preview draft
        resp = requests.post(
            f"{BASE_URL}/skills/import/claude", json=schema, timeout=10
        )
        data = resp.json()
        if not data.get("success"):
            print_result(
                "Import skill (preview)", False, data.get("detail", "Unknown error")
            )
            return False

        draft_id = data.get("draft_id")
        print(f"  Draft created: {draft_id}")

        # Install draft
        resp = requests.post(f"{BASE_URL}/skills/drafts/{draft_id}/install", timeout=10)
        data = resp.json()
        if not data.get("success"):
            print_result("Install skill", False, data.get("error", "Unknown error"))
            return False

        skill_id = data.get("skill_id")
        print(f"  Skill installed: {skill_id}")
        print_result("Import skill", True)
        return True
    except Exception as e:
        print_result("Import skill", False, str(e))
        return False


def test_skill_reload() -> bool:
    """Test skill reload"""
    try:
        resp = requests.post(f"{BASE_URL}/skills/reload-all", timeout=10)
        data = resp.json()
        print_result("Reload all skills", data.get("success", False))
        return data.get("success", False)
    except Exception as e:
        print_result("Reload all skills", False, str(e))
        return False


def test_agents_list() -> bool:
    """Test agents list"""
    print_header("Agent Management")
    try:
        resp = requests.get(f"{BASE_URL}/agents/", timeout=5)
        data = resp.json()
        agents = data.get("agents", [])
        print(f"  Total agents: {len(agents)}")
        for a in agents:
            print(f"    - {a['agent_id']} ({a.get('skill_count', 0)} skills)")
        print_result("List agents", len(agents) > 0)
        return len(agents) > 0
    except Exception as e:
        print_result("List agents", False, str(e))
        return False


def test_agent_details() -> bool:
    """Test agent details"""
    try:
        resp = requests.get(f"{BASE_URL}/agents/research_agent", timeout=5)
        data = resp.json()
        if not data.get("success"):
            print_result("Get agent details", False)
            return False

        agent = data.get("agent", {})
        print(f"  Agent: {agent.get('agent_id')}")
        print(f"  Skills: {len(agent.get('skills', []))}")
        print_result("Get agent details", True)
        return True
    except Exception as e:
        print_result("Get agent details", False, str(e))
        return False


def test_independent_agent_chat() -> bool:
    """Test direct agent chat"""
    print_header("Independent Agent Chat")
    try:
        resp = requests.post(
            f"{BASE_URL}/agents/research_agent/chat",
            json={"message": "Say 'hello' in one word"},
            timeout=30,
        )
        data = resp.json()
        if not data.get("success"):
            print_result("Independent chat", False, data.get("detail", "Unknown"))
            return False

        response = data.get("response", "")
        print(f"  Response: {response[:100]}...")
        print_result("Independent chat", len(response) > 0)
        return len(response) > 0
    except Exception as e:
        print_result("Independent chat", False, str(e))
        return False


def test_memory_stats() -> bool:
    """Test memory stats"""
    print_header("Memory Management")
    try:
        resp = requests.get(f"{BASE_URL}/memory/stats", timeout=5)
        data = resp.json()
        if not data.get("success"):
            print_result("Memory stats", False)
            return False

        stats = data.get("stats", {})
        print(f"  Total memories: {stats.get('total', 0)}")
        print_result("Memory stats", True)
        return True
    except Exception as e:
        print_result("Memory stats", False, str(e))
        return False


def test_memory_add() -> bool:
    """Test adding a memory"""
    try:
        test_id = f"test_{int(time.time())}"
        resp = requests.post(
            f"{BASE_URL}/memory/?text=Test memory {test_id}&session_id={test_id}&owner=test_owner&source=test",
            timeout=5,
        )
        success = resp.status_code == 200
        print_result("Add memory", success)
        return success
    except Exception as e:
        print_result("Add memory", False, str(e))
        return False


def test_memory_search() -> bool:
    """Test memory search"""
    try:
        resp = requests.get(f"{BASE_URL}/memory/search?query=test&top_k=5", timeout=10)
        data = resp.json()
        results = data.get("results", [])
        print(f"  Search results: {len(results)}")
        print_result("Search memory", True)
        return True
    except Exception as e:
        print_result("Search memory", False, str(e))
        return False


def test_memory_list() -> bool:
    """Test memory list"""
    try:
        resp = requests.get(f"{BASE_URL}/memory/?limit=10", timeout=5)
        data = resp.json()
        memories = data.get("memories", [])
        print(f"  Listed memories: {len(memories)}")
        print_result("List memories", True)
        return True
    except Exception as e:
        print_result("List memories", False, str(e))
        return False


def test_evolution_approvals() -> bool:
    """Test evolution approvals"""
    print_header("Evolution Approvals")
    try:
        resp = requests.get(f"{BASE_URL}/evolution/approvals", timeout=5)
        data = resp.json()
        approvals = data.get("approvals", [])
        print(f"  Total approvals: {len(approvals)}")
        print_result("Evolution approvals", True)
        return True
    except Exception as e:
        print_result("Evolution approvals", False, str(e))
        return False


def test_frontend_pages() -> bool:
    """Test frontend pages load"""
    print_header("Frontend Pages")
    pages = [
        ("/", "Main page (index.html)"),
        ("/skills.html", "Skills"),
        ("/agent.html", "Agent"),
        ("/memory.html", "Memory"),
        ("/evolution.html", "Evolution"),
    ]

    all_ok = True
    for path, name in pages:
        try:
            resp = requests.get(f"{BASE_URL}{path}", timeout=5)
            ok = resp.status_code == 200
            print_result(f"Page: {name}", ok, f"HTTP {resp.status_code}")
            if not ok:
                all_ok = False
        except Exception as e:
            print_result(f"Page: {name}", False, str(e))
            all_ok = False

    return all_ok


def test_soul_files() -> bool:
    """Test soul file operations"""
    print_header("Soul Document Management")
    try:
        # List soul files
        resp = requests.get(f"{BASE_URL}/soul/list", timeout=5)
        data = resp.json()
        agents = data.get("agents", [])
        print(f"  Soul files: {len(agents)}")

        # Get soul for research_agent
        resp = requests.get(f"{BASE_URL}/soul/research_agent", timeout=5)
        data = resp.json()
        print_result("Soul files", data.get("exists", False))
        return data.get("exists", False)
    except Exception as e:
        print_result("Soul files", False, str(e))
        return False


def print_summary():
    """Print test summary"""
    print_header("Test Summary")
    passed = sum(1 for r in RESULTS if r["success"])
    failed = len(RESULTS) - passed
    total = len(RESULTS)

    print(f"  Total tests: {total}")
    print(f"  Passed: {passed} ✅")
    print(f"  Failed: {failed} ❌")
    print(f"  Success rate: {passed / total * 100:.1f}%")

    if failed > 0:
        print("\n  Failed tests:")
        for r in RESULTS:
            if not r["success"]:
                print(f"    - {r['name']}: {r['detail']}")

    return failed == 0


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         Agens Multi-Agent System - Test Suite                ║
║                                                              ║
║  Testing all API endpoints and features                     ║
╚══════════════════════════════════════════════════════════════╝
    """)

    print(f"  Base URL: {BASE_URL}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Run all tests
    test_health()
    test_skills_list()
    test_skill_import()
    test_skill_reload()
    test_agents_list()
    test_agent_details()
    test_independent_agent_chat()
    test_memory_stats()
    test_memory_add()
    test_memory_search()
    test_memory_list()
    test_evolution_approvals()
    test_soul_files()
    test_frontend_pages()

    # Print summary
    success = print_summary()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
