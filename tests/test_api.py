#!/usr/bin/env python3
"""
Agens Multi-Agent System - API Test Suite
Tests all backend endpoints and WebSocket functionality
"""

import os
import sys
import time
import json
import asyncio
import subprocess
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")


class colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"


def log_test(name: str, passed: bool, error: str = ""):
    status = (
        f"{colors.GREEN}✓ PASS{colors.END}"
        if passed
        else f"{colors.RED}✗ FAIL{colors.END}"
    )
    print(f"  {status} {name}")
    if error and not passed:
        print(f"      {colors.RED}{error}{colors.END}")
    return passed


class AgensTester:
    def __init__(self):
        self.token: Optional[str] = None
        self.session_id: Optional[str] = None
        self.results = {"passed": 0, "failed": 0}
        self.server_process = None

    def print_header(self, text: str):
        print(f"\n{colors.BLUE}{'=' * 60}{colors.END}")
        print(f"{colors.BLUE}{text}{colors.END}")
        print(f"{colors.BLUE}{'=' * 60}{colors.END}")

    def print_subheader(self, text: str):
        print(f"\n{colors.YELLOW}  {text}{colors.END}")

    def check_server(self) -> bool:
        """Check if server is running"""
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            data = r.json()
            print(f"\n  Server Status: {data.get('status', 'unknown')}")
            print(f"  Provider: {data.get('provider', 'N/A')}")
            print(f"  Model: {data.get('model', 'N/A')}")
            return r.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def wait_for_server(self, timeout: int = 30) -> bool:
        """Wait for server to be ready"""
        print(f"\n  Waiting for server at {BASE_URL}...")
        start = time.time()
        while time.time() - start < timeout:
            if self.check_server():
                return True
            time.sleep(1)
        return False

    # ===== Authentication Tests =====

    def test_auth_login(self) -> bool:
        """Test JWT login"""
        self.print_subheader("Testing Authentication")

        username = os.getenv("ADMIN_USERNAME", "admin")
        password = os.getenv("ADMIN_PASSWORD", "admin")

        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": username, "password": password},
        )

        if r.status_code == 200:
            data = r.json()
            self.token = data.get("access_token")
            if self.token:
                return log_test("Login successful", True)
            return log_test("Login", False, "No token returned")
        else:
            return log_test("Login", False, f"Status {r.status_code}: {r.text}")

    def test_auth_login_invalid(self) -> bool:
        """Test login with invalid credentials"""
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "wrong", "password": "wrong"},
        )
        passed = r.status_code == 401
        return log_test(
            "Login with invalid credentials (should fail)",
            passed,
            f"Expected 401, got {r.status_code}",
        )

    def test_auth_me(self) -> bool:
        """Test get current user"""
        if not self.token:
            return log_test("Get current user", False, "No token available")

        r = requests.get(
            f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {self.token}"}
        )

        if r.status_code == 200:
            data = r.json()
            return log_test(f"Get current user: {data.get('username')}", True)
        return log_test("Get current user", False, f"Status {r.status_code}")

    def test_auth_me_unauthorized(self) -> bool:
        """Test get current user without token"""
        r = requests.get(f"{BASE_URL}/api/auth/me")
        passed = r.status_code == 401
        return log_test("Get current user without token (should fail)", passed)

    def test_auth_logout(self) -> bool:
        """Test logout"""
        if not self.token:
            return log_test("Logout", False, "No token available")

        r = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        return log_test("Logout", r.status_code == 200, f"Status {r.status_code}")

    # ===== Health & System Tests =====

    def test_health(self) -> bool:
        """Test health endpoint"""
        r = requests.get(f"{BASE_URL}/health")
        data = r.json()
        passed = r.status_code == 200 and data.get("status") == "healthy"
        return log_test("Health check", passed, f"Status: {data.get('status')}")

    def test_providers(self) -> bool:
        """Test providers endpoint"""
        r = requests.get(f"{BASE_URL}/providers")
        data = r.json()
        passed = r.status_code == 200 and isinstance(data, list)
        if passed:
            print(f"\n    Providers: {len(data)} available")
        return log_test(f"List providers ({len(data)} providers)", passed)

    def test_agents(self) -> bool:
        """Test agents endpoint"""
        r = requests.get(f"{BASE_URL}/agents/")
        data = r.json()
        passed = r.status_code == 200 and "agents" in data
        if passed:
            print(f"\n    Agents: {len(data.get('agents', []))} registered")
        return log_test(f"List agents ({len(data.get('agents', []))} agents)", passed)

    def test_skills(self) -> bool:
        """Test skills endpoint"""
        r = requests.get(f"{BASE_URL}/skills")
        data = r.json()
        passed = r.status_code == 200 and isinstance(data, list)
        if passed:
            print(f"\n    Skills: {len(data)} installed")
        return log_test(f"List skills ({len(data)} skills)", passed)

    def test_hooks(self) -> bool:
        """Test hooks endpoint"""
        r = requests.get(f"{BASE_URL}/hooks")
        data = r.json()
        passed = r.status_code == 200 and isinstance(data, list)
        return log_test("List hooks", passed)

    def test_memory_stats(self) -> bool:
        """Test memory stats endpoint"""
        r = requests.get(f"{BASE_URL}/memory/stats")
        data = r.json()
        passed = r.status_code == 200 and "total" in data
        if passed:
            print(f"\n    Memory: {data.get('total')} items stored")
        return log_test(f"Memory stats ({data.get('total')} items)", passed)

    # ===== Sessions Tests =====

    def test_sessions_list(self) -> bool:
        """Test list sessions"""
        r = requests.get(f"{BASE_URL}/sessions")
        data = r.json()
        passed = r.status_code == 200 and isinstance(data, list)
        return log_test(f"List sessions ({len(data)} sessions)", passed)

    def test_session_create(self) -> bool:
        """Test create session"""
        r = requests.post(f"{BASE_URL}/sessions?title=Test Session")
        data = r.json()
        passed = r.status_code == 200 and "session_id" in data
        if passed:
            self.session_id = data.get("session_id")
            print(f"\n    Created session: {self.session_id[:8]}...")
        return log_test("Create session", passed)

    def test_session_get(self) -> bool:
        """Test get session"""
        if not self.session_id:
            return log_test("Get session", False, "No session_id")

        r = requests.get(f"{BASE_URL}/sessions/{self.session_id}")
        passed = r.status_code == 200
        return log_test(f"Get session", passed)

    def test_session_delete(self) -> bool:
        """Test delete session"""
        if not self.session_id:
            return log_test("Delete session", False, "No session_id")

        r = requests.delete(f"{BASE_URL}/sessions/{self.session_id}")
        passed = r.status_code == 200
        if passed:
            self.session_id = None
        return log_test("Delete session", passed)

    # ===== Chat Tests =====

    def test_chat_stream(self) -> bool:
        """Test chat streaming endpoint"""
        if not self.token:
            return log_test("Chat stream", False, "No token available")

        print(f"\n    Sending message to chat stream...")
        try:
            r = requests.post(
                f"{BASE_URL}/chat/stream",
                json={"message": "Hello, what can you do?"},
                headers={"Authorization": f"Bearer {self.token}"},
                stream=True,
                timeout=60,
            )

            if r.status_code == 200:
                events = []
                for line in r.iter_lines():
                    if line:
                        decoded = line.decode("utf-8")
                        if decoded.startswith("data: "):
                            try:
                                data = json.loads(decoded[6:])
                                event_type = data.get("event", "unknown")
                                events.append(event_type)
                                if event_type == "done":
                                    break
                            except json.JSONDecodeError:
                                pass

                print(f"\n    Received {len(events)} events: {events}")
                return log_test("Chat stream (received events)", True)
            else:
                return log_test("Chat stream", False, f"Status {r.status_code}")
        except requests.exceptions.Timeout:
            return log_test("Chat stream", False, "Timeout")
        except Exception as e:
            return log_test("Chat stream", False, str(e))

    # ===== WebSocket Tests =====

    def test_websocket_connection(self) -> bool:
        """Test WebSocket connection"""
        try:
            import websocket

            ws_url = BASE_URL.replace("http", "ws") + "/ws/events"
            print(f"\n    Connecting to {ws_url}...")

            ws = websocket.create_connection(ws_url, timeout=10)
            ws.settimeout(5)

            # Send ping
            ws.ping("ping")

            # Try to receive
            try:
                msg = ws.recv()
                print(f"\n    Received: {msg[:100]}...")
            except websocket.WebSocketTimeoutException:
                pass

            ws.close()
            return log_test("WebSocket connection", True)
        except ImportError:
            print("\n    websocket-client not installed, skipping...")
            return log_test(
                "WebSocket connection", True, "websocket-client not installed (skipped)"
            )
        except Exception as e:
            return log_test("WebSocket connection", False, str(e))

    # ===== Skills Tests =====

    def test_skill_search(self) -> bool:
        """Test skill search"""
        r = requests.get(f"{BASE_URL}/skills/search?q=web")
        data = r.json()
        passed = r.status_code == 200 and isinstance(data, list)
        return log_test("Search skills", passed)

    # ===== Memory Tests =====

    def test_memory_list(self) -> bool:
        """Test memory list"""
        r = requests.get(f"{BASE_URL}/memory/?limit=10")
        data = r.json()
        passed = r.status_code == 200 and "memories" in data
        if passed:
            print(f"\n    Memories: {len(data.get('memories', []))} shown")
        return log_test("List memories", passed)

    def test_memory_add(self) -> bool:
        """Test add memory"""
        r = requests.post(
            f"{BASE_URL}/memory/?text=Test memory from API&session_id=test_session&owner=global&source=test"
        )
        passed = r.status_code == 200
        if passed:
            print("\n    Added test memory")
        return log_test("Add memory", passed)

    def test_memory_search(self) -> bool:
        """Test memory search"""
        r = requests.get(f"{BASE_URL}/memory/search?query=test&top_k=5")
        data = r.json()
        passed = r.status_code == 200 and "results" in data
        if passed:
            print(f"\n    Found {len(data.get('results', []))} results")
        return log_test("Search memories", passed)

    # ===== Approvals Tests =====

    def test_approvals_list(self) -> bool:
        """Test list approvals"""
        r = requests.get(f"{BASE_URL}/approvals")
        data = r.json()
        passed = r.status_code == 200 and "approvals" in data
        if passed:
            pending = [a for a in data["approvals"] if a.get("status") == "pending"]
            print(
                f"\n    Approvals: {len(data['approvals'])} total, {len(pending)} pending"
            )
        return log_test("List approvals", passed)

    # ===== Run All Tests =====

    def run_all_tests(self):
        """Run all tests"""
        self.print_header("Agens Multi-Agent System - API Test Suite")
        print(f"\n  API Base URL: {BASE_URL}")
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if not self.wait_for_server():
            print(
                f"\n{colors.RED}  ERROR: Server not available at {BASE_URL}{colors.END}"
            )
            print(f"  Please start the server first:")
            print(f"  python -m uvicorn api.main:app --reload --port 8000")
            return

        tests = [
            (
                "Authentication",
                [
                    self.test_auth_login,
                    self.test_auth_login_invalid,
                    self.test_auth_me,
                    self.test_auth_me_unauthorized,
                    self.test_auth_logout,
                ],
            ),
            (
                "System",
                [
                    self.test_health,
                    self.test_providers,
                    self.test_agents,
                    self.test_skills,
                    self.test_hooks,
                    self.test_memory_stats,
                ],
            ),
            (
                "Sessions",
                [
                    self.test_sessions_list,
                    self.test_session_create,
                    self.test_session_get,
                    self.test_session_delete,
                ],
            ),
            (
                "Chat",
                [
                    self.test_chat_stream,
                ],
            ),
            (
                "WebSocket",
                [
                    self.test_websocket_connection,
                ],
            ),
            (
                "Skills",
                [
                    self.test_skill_search,
                ],
            ),
            (
                "Memory",
                [
                    self.test_memory_list,
                    self.test_memory_add,
                    self.test_memory_search,
                ],
            ),
            (
                "Approvals",
                [
                    self.test_approvals_list,
                ],
            ),
        ]

        for category, test_funcs in tests:
            self.print_header(category)
            for test in test_funcs:
                try:
                    passed = test()
                    if passed:
                        self.results["passed"] += 1
                    else:
                        self.results["failed"] += 1
                except Exception as e:
                    log_test(test.__name__, False, str(e))
                    self.results["failed"] += 1

        self.print_header("Test Results")
        total = self.results["passed"] + self.results["failed"]
        print(f"\n  {colors.GREEN}Passed: {self.results['passed']}{colors.END}")
        print(f"  {colors.RED}Failed: {self.results['failed']}{colors.END}")
        print(f"  Total:  {total}")

        if self.results["failed"] == 0:
            print(f"\n{colors.GREEN}  All tests passed!{colors.END}")
        else:
            print(f"\n{colors.RED}  Some tests failed.{colors.END}")

        return self.results["failed"] == 0


def install_dependencies():
    """Install required Python packages"""
    print("\nInstalling required packages...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-q",
            "requests",
            "python-dotenv",
            "websocket-client",
        ],
        check=True,
    )


if __name__ == "__main__":
    install_dependencies()

    tester = AgensTester()
    success = tester.run_all_tests()

    sys.exit(0 if success else 1)
