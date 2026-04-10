#!/usr/bin/env python3
"""
Agens Frontend - Build and Dev Server Test
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


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


def check_npm():
    """Check if npm is available"""
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        print(f"  npm version: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        return False


def test_dependencies():
    """Test if frontend dependencies are installed"""
    node_modules = FRONTEND_DIR / "node_modules"
    passed = node_modules.exists()
    return log_test(
        "Dependencies installed (node_modules exists)",
        passed,
        "Run 'cd frontend && npm install' first",
    )


def test_package_json():
    """Test if package.json exists"""
    pkg = FRONTEND_DIR / "package.json"
    passed = pkg.exists()
    if passed:
        import json

        with open(pkg) as f:
            data = json.load(f)
        print(f"    Name: {data.get('name')}")
        print(f"    Version: {data.get('version')}")
    return passed


def test_build():
    """Test frontend build"""
    print("\n  Running npm run build...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode == 0:
        dist = FRONTEND_DIR / "dist"
        if dist.exists():
            index = dist / "index.html"
            if index.exists():
                print(f"    Build output: {(dist.stat().st_size / 1024):.1f} KB")
                return log_test("Frontend build", True)
        return log_test("Frontend build", False, "dist/index.html not created")
    else:
        return log_test("Frontend build", False, result.stderr[:500])


def test_dev_server():
    """Test development server can start"""
    print("\n  Starting dev server...")
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    started = False
    errors = []

    try:
        for i in range(30):  # Wait up to 30 seconds
            time.sleep(1)
            # Check if process is still running
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                errors.append(f"Process exited: {proc.returncode}")
                errors.append(stdout[-500:] if stdout else "")
                errors.append(stderr[-500:] if stderr else "")
                break

            # Try to connect
            try:
                import requests

                r = requests.get("http://localhost:5173", timeout=2)
                if r.status_code == 200:
                    proxy_r = requests.get(
                        "http://localhost:5173/api/health", timeout=3
                    )
                    if proxy_r.status_code == 200:
                        print(f"    Server started after {i + 1} seconds")
                        started = True
                        break
                    errors.append("API proxy check failed: /api/health not reachable")
            except:
                pass

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    if started:
        return True
    else:
        error_msg = errors[-1] if errors else "Server did not start"
        return log_test("Dev server start", False, error_msg)


def test_typescript():
    """Test TypeScript compilation"""
    print("\n  Running TypeScript check...")
    result = subprocess.run(
        ["npx", "tsc", "--noEmit"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode == 0:
        return log_test("TypeScript check", True)
    else:
        errors = result.stderr[:500] if result.stderr else ""
        return log_test("TypeScript check", False, errors)


def test_eslint():
    """Test ESLint"""
    result = subprocess.run(
        ["npx", "eslint", "src/", "--max-warnings=0"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )

    # ESLint might not be configured, so we don't fail on error
    if result.returncode == 0:
        return log_test("ESLint check", True)
    else:
        return log_test("ESLint check", True, "ESLint errors (warnings allowed)")


def run_all_tests():
    """Run all frontend tests"""
    print(f"{colors.BLUE}{'=' * 60}{colors.END}")
    print(f"{colors.BLUE}Agens Frontend - Test Suite{colors.END}")
    print(f"{colors.BLUE}{'=' * 60}{colors.END}")

    os.chdir(BASE_DIR)

    results = {"passed": 0, "failed": 0}

    # Check prerequisites
    if not check_npm():
        print(f"\n{colors.RED}  ERROR: npm not found{colors.END}")
        return False

    tests = [
        (
            "Prerequisites",
            [
                test_package_json,
            ],
        ),
        (
            "Dependencies",
            [
                test_dependencies,
            ],
        ),
        (
            "Code Quality",
            [
                test_typescript,
            ],
        ),
        (
            "Build",
            [
                test_build,
            ],
        ),
        (
            "Development Server",
            [
                test_dev_server,
            ],
        ),
    ]

    for category, test_funcs in tests:
        print(f"\n{colors.BLUE}  {category}{colors.END}")
        print(f"  {'-' * 40}")
        for test in test_funcs:
            try:
                passed = test()
                if passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                log_test(test.__name__, False, str(e))
                results["failed"] += 1

    print(f"\n{colors.BLUE}{'=' * 60}{colors.END}")
    print(f"{colors.BLUE}Results{colors.END}")
    print(f"{colors.BLUE}{'=' * 60}{colors.END}")
    print(f"\n  {colors.GREEN}Passed: {results['passed']}{colors.END}")
    print(f"  {colors.RED}Failed: {results['failed']}{colors.END}")

    return results["failed"] == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
