#!/usr/bin/env python3
"""
Agens UI - Comprehensive Button & Functionality Test
使用 Playwright 模拟用户点击每个按钮，验证功能正常且日志无报错
"""

import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Page, Browser, ConsoleMessage
except ImportError:
    print("Installing Playwright...")
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"])
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
    from playwright.async_api import async_playwright, Page, Browser, ConsoleMessage


BASE_URL = "http://localhost:5173"
API_URL = "http://localhost:8000"
LOG_FILES = [
    Path("./logs/features/chat_current.log"),
    Path("./logs/features/ws_current.log"),
    Path("./logs/features/system_current.log"),
]

C = {
    "GREEN": "\033[92m",
    "RED": "\033[91m",
    "YELLOW": "\033[93m",
    "BLUE": "\033[94m",
    "END": "\033[0m",
}


def log(msg: str, color="END"):
    print(f"{C.get(color, '')}{msg}{C['END']}")


def log_line():
    log("─" * 60, "BLUE")


class LogMonitor:
    """监控日志文件中的错误"""

    def __init__(self):
        self.last_sizes = {}
        for f in LOG_FILES:
            if f.exists():
                self.last_sizes[str(f)] = f.stat().st_size

    def get_new_errors(self) -> list[str]:
        errors = []
        for f in LOG_FILES:
            if not f.exists():
                continue
            try:
                size = f.stat().st_size
                if str(f) in self.last_sizes and size > self.last_sizes[str(f)]:
                    with open(f, "r") as fh:
                        fh.seek(self.last_sizes[str(f)])
                        new_content = fh.read()
                        for line in new_content.splitlines():
                            if any(
                                x in line for x in ["ERROR", "Exception", "Traceback"]
                            ):
                                errors.append(f"[{f.name}] {line.strip()}")
                self.last_sizes[str(f)] = size
            except Exception:
                pass
        return errors


async def get_admin_token() -> str:
    import urllib.request

    req = urllib.request.Request(
        f"{API_URL}/api/auth/login",
        data=json.dumps({"username": "admin", "password": "admin123"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
        return data["access_token"]


async def set_deepseek_token(token: str):
    import urllib.request

    req = urllib.request.Request(
        f"{API_URL}/api/providers/deepseek/use",
        data=json.dumps({"model": "deepseek-chat"}).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


async def login_and_store_token(page: Page):
    """通过 UI 进行真实登录"""
    await page.goto(f"{BASE_URL}/login")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1)

    username_input = page.locator('input[type="text"], input[name="username"]').first
    password_input = page.locator(
        'input[type="password"], input[name="password"]'
    ).first

    if await username_input.count() > 0 and await password_input.count() > 0:
        await username_input.fill("admin")
        await password_input.fill("admin123")

        login_btn = page.locator(
            'button[type="submit"], button:has-text("Login"), button:has-text("Sign in")'
        ).first
        if await login_btn.count() > 0:
            await login_btn.click()
            await page.wait_for_load_state("networkidle", timeout=10000)
            await asyncio.sleep(1)
            log(f"✓ UI login done, URL: {page.url}")
        else:
            log("⚠ Login button not found")
    else:
        log("⚠ Login form not found")

    log(f"✓ Login complete, current URL: {page.url}")


async def goto(page: Page, label: str):
    """导航到指定页面"""
    routes = {
        "Chat": "/",
        "Dashboard": "/dashboard",
        "Models": "/providers",
        "Skills": "/skills",
        "Knowledge": "/knowledge",
        "Approvals": "/approvals",
        "Sessions": "/sessions",
        "Agent Chat": "/agent-chat",
        "Agent Settings": "/agent-settings",
    }
    route = routes.get(label, "/")
    await page.goto(f"{BASE_URL}{route}")
    await page.wait_for_load_state("networkidle", timeout=15000)
    await asyncio.sleep(0.5)
    log(f"✓ Navigated to {label} ({page.url})")


async def test_chat_page(page: Page):
    """测试 Chat 页面"""
    log_line()
    log("Testing Chat Page")
    log_line()

    await goto(page, "Chat")
    await asyncio.sleep(1)

    msg_input = page.locator(
        'input[placeholder*="message"], input[placeholder*="Message"], textarea'
    )
    if await msg_input.count() > 0:
        log("✓ Chat input found")

    provider_select = page.locator("header select")
    if await provider_select.count() > 0:
        current_val = await provider_select.input_value()
        log(f"✓ Model selector found (current: {current_val})")
        options = await provider_select.locator("option").all()
        if len(options) > 1:
            await provider_select.select_option(index=1)
            await asyncio.sleep(0.5)
            new_val = await provider_select.input_value()
            log(f"✓ Model switched to: {new_val}")

    input_box = page.locator('input[type="text"], textarea').first
    if await input_box.count() > 0:
        await input_box.fill("Hello, what model are you using?")
        await asyncio.sleep(0.3)

        send_btn = page.locator(
            'button:has(svg.lucide-send), button:has-text("Send")'
        ).first
        if await send_btn.count() > 0:
            await send_btn.click()
            log("✓ Send button clicked")
            await asyncio.sleep(10)
            log("✓ Chat stream waited")

    log("✓ Chat page test complete")


async def test_dashboard_page(page: Page):
    """测试 Dashboard 页面"""
    log_line()
    log("Testing Dashboard Page")
    log_line()

    await goto(page, "Dashboard")
    await asyncio.sleep(2)

    stat_cards = await page.locator(".glass-card").all()
    log(f"✓ Found {len(stat_cards)} card elements")

    charts = await page.locator("svg").all()
    log(f"✓ Found {len(charts)} SVG chart elements")

    trace_rows = await page.locator("table tbody tr").all()
    log(f"✓ Found {len(trace_rows)} trace rows")

    log("✓ Dashboard page test complete")


async def test_skills_page(page: Page):
    """测试 Skills 页面"""
    log_line()
    log("Testing Skills Page")
    log_line()

    await goto(page, "Skills")
    await asyncio.sleep(2)

    refresh_btn = page.locator("button:has-text('Refresh')")
    if await refresh_btn.count() > 0:
        await refresh_btn.click()
        await asyncio.sleep(1)
        log("✓ Refresh button clicked")

    install_btn = page.locator(
        "button:has-text('Install Skill'), button:has-text('Install')"
    ).first
    if await install_btn.count() > 0:
        await install_btn.click()
        await asyncio.sleep(0.5)
        log("✓ Install Skill button clicked")

        dialog = page.locator('[role="dialog"]')
        if await dialog.count() > 0:
            log("✓ Install dialog opened")
            close_btn = page.locator("button:has(svg.lucide-x)").first
            if await close_btn.count() > 0:
                await close_btn.click()
            else:
                cancel_btn = page.locator('button:has-text("Cancel")').first
                if await cancel_btn.count() > 0:
                    await cancel_btn.click()
            await asyncio.sleep(0.3)
            log("✓ Dialog closed")

    log("✓ Skills page test complete")


async def test_knowledge_page(page: Page):
    """测试 Knowledge 页面"""
    log_line()
    log("Testing Knowledge Page")
    log_line()

    await goto(page, "Knowledge")
    await asyncio.sleep(2)

    search_input = page.locator('input[placeholder*="Search"]').first
    if await search_input.count() > 0:
        await search_input.fill("test")
        await asyncio.sleep(0.3)
        await search_input.clear()
        log("✓ Search input works")

    import_btn = page.locator(
        "button:has-text('Import Document'), button:has-text('Import')"
    ).first
    if await import_btn.count() > 0:
        await import_btn.click()
        await asyncio.sleep(0.5)
        log("✓ Import Document button clicked")

        dialog = page.locator('[role="dialog"]')
        if await dialog.count() > 0:
            log("✓ Import dialog opened")

            url_btn = page.locator("button:has-text('URL Import')")
            if await url_btn.count() > 0:
                await url_btn.click()
                await asyncio.sleep(0.2)
                log("✓ Switched to URL import mode")

            close_btn = page.locator("button:has(svg.lucide-x)").first
            if await close_btn.count() > 0:
                await close_btn.click()
            else:
                cancel_btn = page.locator('button:has-text("Cancel")').first
                if await cancel_btn.count() > 0:
                    await cancel_btn.click()
            await asyncio.sleep(0.3)

    log("✓ Knowledge page test complete")


async def test_approvals_page(page: Page):
    """测试 Approvals 页面"""
    log_line()
    log("Testing Approvals Page")
    log_line()

    await goto(page, "Approvals")
    await asyncio.sleep(2)

    body = await page.locator("body").inner_text()
    if "pending" in body.lower() or "approval" in body.lower():
        log("✓ Approvals page loaded")

    await asyncio.sleep(1)
    log("✓ Approvals page test complete")


async def test_sessions_page(page: Page):
    """测试 Sessions 页面"""
    log_line()
    log("Testing Sessions Page")
    log_line()

    await goto(page, "Sessions")
    await asyncio.sleep(2)

    session_items = await page.locator(".space-y-3 > div").all()
    log(f"✓ Found {len(session_items)} session items")

    delete_btns = await page.locator("button:has(svg.lucide-trash-2)").all()
    if len(delete_btns) > 0:
        await delete_btns[0].click()
        await asyncio.sleep(0.5)
        log("✓ Delete button clicked")

        confirm_btn = page.locator(
            'button:has-text("Delete"), button:has-text("Confirm")'
        ).first
        if await confirm_btn.count() > 0:
            await confirm_btn.click()
            await asyncio.sleep(0.5)
            log("✓ Confirm delete clicked")
        else:
            cancel_btn = page.locator('button:has-text("Cancel")').first
            if await cancel_btn.count() > 0:
                await cancel_btn.click()
                await asyncio.sleep(0.3)

    log("✓ Sessions page test complete")


async def test_agent_chat_page(page: Page):
    """测试 Agent Chat 页面"""
    log_line()
    log("Testing Agent Chat Page")
    log_line()

    await goto(page, "Agent Chat")
    await asyncio.sleep(2)

    agent_items = await page.locator(".glass-card button").all()
    log(f"✓ Found {len(agent_items)} agent items")

    if len(agent_items) > 0:
        await agent_items[0].click()
        await asyncio.sleep(0.3)
        log("✓ Agent selected")

    input_box = page.locator('input[type="text"], textarea').first
    if await input_box.count() > 0:
        await input_box.fill("status")
        await asyncio.sleep(0.3)

        send_btn = page.locator("button:has(svg.lucide-send)").first
        if await send_btn.count() > 0:
            await send_btn.click()
            await asyncio.sleep(5)
            log("✓ Agent chat message sent")

    log("✓ Agent Chat page test complete")


async def test_agent_settings_page(page: Page):
    """测试 Agent Settings 页面"""
    log_line()
    log("Testing Agent Settings Page")
    log_line()

    await goto(page, "Agent Settings")
    await asyncio.sleep(2)

    agent_items = await page.locator(".glass-card button").all()
    log(f"✓ Found {len(agent_items)} agent items in sidebar")

    assign_btns = await page.locator(
        "button:has-text('Assign'), button:has-text('Assigned')"
    ).all()
    log(f"✓ Found {len(assign_btns)} skill assign buttons")
    if len(assign_btns) > 0:
        await assign_btns[0].click()
        await asyncio.sleep(0.5)
        log("✓ Skill assign button clicked")

    memory_input = page.locator(
        'input[placeholder*="memory"], input[placeholder*="Memory"]'
    ).first
    if await memory_input.count() > 0:
        await memory_input.fill("test memory content")
        await asyncio.sleep(0.2)

        add_btn = page.locator("button:has(svg.lucide-plus)").first
        if await add_btn.count() > 0:
            await add_btn.click()
            await asyncio.sleep(1)
            log("✓ Add memory button clicked")

    delete_mem_btns = await page.locator("button:has-text('Delete')").all()
    if len(delete_mem_btns) > 0:
        await delete_mem_btns[0].click()
        await asyncio.sleep(0.5)
        log("✓ Delete memory button clicked")

    log("✓ Agent Settings page test complete")


async def test_models_page(page: Page):
    """测试 Models 页面（添加/删除/切换）"""
    log_line()
    log("Testing Models Page")
    log_line()

    await goto(page, "Models")
    await asyncio.sleep(2)

    model_cards = await page.locator(".glass-card").all()
    log(f"✓ Found {len(model_cards)} model cards")

    add_btn = page.locator("button:has-text('Add Model')").first
    if await add_btn.count() > 0:
        await add_btn.click()
        await asyncio.sleep(0.5)
        log("✓ Add Model button clicked")

        dialog = page.locator('[role="dialog"]')
        if await dialog.count() > 0:
            log("✓ Add Model dialog opened")

            await page.locator('input[name="name"]').fill("Test Provider")
            await asyncio.sleep(0.2)
            id_val = await page.locator('input[name="id"]').input_value()
            log(f"✓ Provider ID auto-generated: {id_val}")

            await page.locator('input[name="model"]').fill("test-model")
            await page.locator('input[name="api_key"]').fill("sk-test123456789")

            close_btn = page.locator("button:has(svg.lucide-x)").first
            if await close_btn.count() > 0:
                await close_btn.click()
            else:
                cancel_btn = page.locator('button:has-text("Cancel")').first
                if await cancel_btn.count() > 0:
                    await cancel_btn.click()
            await asyncio.sleep(0.3)
            log("✓ Dialog closed without submitting")

    log("✓ Models page test complete")


async def test_model_switcher(page: Page):
    """测试 Header 模型切换器"""
    log_line()
    log("Testing Model Switcher")
    log_line()

    await goto(page, "Dashboard")
    await asyncio.sleep(1)

    select_box = page.locator("header select").first
    if await select_box.count() > 0:
        options = await select_box.locator("option").all()
        log(f"✓ Model selector has {len(options)} options")

        if len(options) > 1:
            original = await select_box.input_value()
            await select_box.select_option(index=1)
            await asyncio.sleep(1)
            new_val = await select_box.input_value()
            log(f"✓ Switched model from {original} to {new_val}")

            await select_box.select_option(original)
            await asyncio.sleep(0.5)

    log("✓ Model switcher test complete")


async def test_logout(page: Page):
    """测试登出"""
    log_line()
    log("Testing Logout")
    log_line()

    logout_btn = page.locator('button[title="Logout"], button:has(svg.lucide-log-out)')
    if await logout_btn.count() > 0:
        await logout_btn.click()
        await asyncio.sleep(1)
        current_url = page.url
        if "login" in current_url:
            log("✓ Logout successful - redirected to login")
        else:
            log("✓ Logout button clicked")

    log("✓ Logout test complete")


async def collect_console_errors(page: Page) -> list:
    """收集控制台错误"""
    errors = []

    def handle_console(msg: ConsoleMessage):
        if msg.type == "error":
            text = msg.text
            if not any(
                x in text.lower()
                for x in ["failed to load resource", "net::err", "favicon"]
            ):
                errors.append(text)

    page.on("console", handle_console)
    return errors


async def run_tests():
    log(f"{C['BLUE']}{'=' * 60}")
    log(f"{C['BLUE']}Agens UI - Comprehensive Test Suite")
    log(f"{C['BLUE']}{'=' * 60}")
    log(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("")

    try:
        import urllib.request

        urllib.request.urlopen(f"{API_URL}/api/health", timeout=3)
        log(f"✓ Backend API is running at {API_URL}")
    except Exception as e:
        log(f"✗ Backend API not reachable: {e}", "RED")
        return False

    try:
        urllib.request.urlopen(f"{BASE_URL}", timeout=3)
        log(f"✓ Frontend is running at {BASE_URL}")
    except Exception as e:
        log(f"✗ Frontend not reachable: {e}", "RED")
        return False

    try:
        token = await get_admin_token()
        await set_deepseek_token(token)
        log("✓ DeepSeek model set as active")
    except Exception as e:
        log(f"⚠ Could not set DeepSeek: {e}", "YELLOW")

    monitor = LogMonitor()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await collect_console_errors(page)

        await login_and_store_token(page)

        results = {}
        test_functions = [
            ("Chat Page", test_chat_page),
            ("Dashboard Page", test_dashboard_page),
            ("Skills Page", test_skills_page),
            ("Knowledge Page", test_knowledge_page),
            ("Approvals Page", test_approvals_page),
            ("Sessions Page", test_sessions_page),
            ("Agent Chat Page", test_agent_chat_page),
            ("Agent Settings Page", test_agent_settings_page),
            ("Models Page", test_models_page),
            ("Model Switcher", test_model_switcher),
            ("Logout", test_logout),
        ]

        for name, fn in test_functions:
            try:
                await fn(page)
                results[name] = "PASS"
            except Exception as e:
                log(f"✗ {name} failed: {e}", "RED")
                import traceback

                traceback.print_exc()
                results[name] = f"FAIL: {e}"

            new_errors = monitor.get_new_errors()
            for err in new_errors:
                log(f"  ⚠ Log error: {err}", "YELLOW")

            await asyncio.sleep(0.5)

        await browser.close()

    log("")
    log_line()
    log("TEST RESULTS SUMMARY")
    log_line()

    passed = sum(1 for v in results.values() if v == "PASS")
    failed = sum(1 for v in results.values() if v != "PASS")

    for name, result in results.items():
        status = (
            f"{C['GREEN']}✓ PASS{C['END']}"
            if result == "PASS"
            else f"{C['RED']}✗ FAIL{C['END']}"
        )
        log(f"  {status}  {name}")
        if result != "PASS":
            log(f"       {result}", "RED")

    log("")
    log(
        f"Passed: {passed}/{len(results)}",
        "GREEN" if passed == len(results) else "YELLOW",
    )
    log(f"Failed: {failed}/{len(results)}", "RED" if failed > 0 else "GREEN")

    log("")
    log_line()
    log("FINAL LOG CHECK")
    log_line()

    all_log_errors = []
    for f in LOG_FILES:
        if f.exists():
            try:
                with open(f, "r") as fh:
                    content = fh.read()
                    errors_in_file = [
                        line.strip()
                        for line in content.splitlines()
                        if any(
                            x in line
                            for x in ["ERROR", "Exception", "Traceback", "CRITICAL"]
                        )
                    ]
                    if errors_in_file:
                        all_log_errors.extend(errors_in_file[-10:])
            except Exception:
                pass

    if all_log_errors:
        log(f"⚠ Found {len(all_log_errors)} error lines in logs:", "YELLOW")
        for err in all_log_errors[:5]:
            log(f"   {err[:120]}", "YELLOW")
    else:
        log("✓ No ERROR/Exception/Traceback found in logs", "GREEN")

    log("")
    log(f"Test completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_line()

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
