#!/usr/bin/env python3
"""
Multi-Agent Dashboard - Client TUI Application
A standalone terminal UI for multi-agent orchestration
Features: Day/Night mode, Real-time Agent Monitoring, Step-by-step Results
"""

import os
import sys
import time
import asyncio
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.live import Live
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax
    from rich.prompt import Prompt, Confirm
    from rich.tree import Tree
    from rich.columns import Columns
except ImportError:
    print("Error: rich library not installed. Run: pip install rich")
    sys.exit(1)


class Theme:
    DARK = {
        "bg_primary": "#0d1117",
        "bg_secondary": "#161b22",
        "bg_tertiary": "#21262d",
        "accent_blue": "#58a6ff",
        "accent_green": "#3fb950",
        "accent_red": "#f85149",
        "accent_orange": "#d29922",
        "accent_purple": "#a371f7",
        "text_primary": "#e6edf3",
        "text_secondary": "#8b949e",
        "text_muted": "#6e7681",
        "border": "#30363d",
    }

    LIGHT = {
        "bg_primary": "#ffffff",
        "bg_secondary": "#f6f8fa",
        "bg_tertiary": "#eaeef2",
        "accent_blue": "#0969da",
        "accent_green": "#1a7f37",
        "accent_red": "#cf222e",
        "accent_orange": "#9a6700",
        "accent_purple": "#8250df",
        "text_primary": "#1f2328",
        "text_secondary": "#656d76",
        "text_muted": "#8c959f",
        "border": "#d0d7de",
    }


class AgentStatus(Enum):
    ONLINE = "online"
    RUNNING = "running"
    ERROR = "error"
    OFFLINE = "offline"


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class TaskStep:
    def __init__(self, agent: str, instruction: str):
        self.agent = agent
        self.instruction = instruction
        self.status = StepStatus.PENDING
        self.result: Optional[str] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    @property
    def duration(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


class AgentState:
    def __init__(self, agent_id: str, icon: str, description: str):
        self.agent_id = agent_id
        self.icon = icon
        self.description = description
        self.status = AgentStatus.ONLINE
        self.current_task = "Idle"
        self.last_update = time.time()


class MultiAgentDashboard:
    def __init__(self):
        self.console = Console()
        self.theme = Theme.DARK
        self.is_dark = True
        self.current_page = "overview"
        self.messages: List[Dict] = []
        self.task_steps: List[TaskStep] = []
        self.current_task_id: Optional[str] = None
        self.running = True

        # Initialize agents
        self.agents = {
            "orchestrator": AgentState(
                "orchestrator", "🎯", "Task planning & dispatch"
            ),
            "research_agent": AgentState(
                "research_agent", "🔍", "Web search & analysis"
            ),
            "executor_agent": AgentState(
                "executor_agent", "⚡", "Code execution & tools"
            ),
            "writer_agent": AgentState("writer_agent", "✍️", "Content generation"),
        }

        self._update_styles()

    def _update_styles(self):
        """Update Rich console theme"""
        # Theme is handled by the console's own rendering
        pass

    def toggle_theme(self):
        """Toggle between dark and light mode"""
        self.is_dark = not self.is_dark
        self.theme = Theme.DARK if self.is_dark else Theme.LIGHT
        self._update_styles()

    def clear_screen(self):
        """Clear the console"""
        self.console.clear()

    def render_header(self):
        """Render application header"""
        theme = self.theme
        title = Text()
        title.append("> ", style=f"bold {theme['accent_blue']}")
        title.append("Multi-Agent Dashboard", style=f"bold {theme['text_primary']}")
        title.append("  v2.0.0", style=f"{theme['text_muted']}")

        mode_text = "🌙 Dark" if self.is_dark else "☀️ Light"

        self.console.print(
            Panel(
                title,
                title=f"[{theme['text_muted']}]{mode_text} Mode[/] | [Press 't' to toggle theme]",
                style=theme["bg_secondary"],
                border_style=theme["border"],
                height=3,
            )
        )

    def render_sidebar(self) -> str:
        """Render sidebar navigation, return selected page"""
        theme = self.theme

        pages = [
            ("overview", "🏠 Overview", "Dashboard overview and metrics"),
            ("monitor", "🤖 Agent Monitor", "Real-time agent status"),
            ("results", "📊 Task Results", "Step-by-step execution results"),
            ("chat", "💬 Chat", "Task input and execution"),
            ("providers", "🔌 Providers", "Model provider configuration"),
            ("skills", "🧩 Skills", "Installed skills management"),
            ("config", "⚙️ Config", "System configuration"),
        ]

        table = Table(show_header=False, box=None, padding=0, pad_edge=False)
        table.add_column(style=theme["text_secondary"])

        for page_id, icon_name, desc in pages:
            marker = "▶ " if self.current_page == page_id else "  "
            style = (
                theme["accent_blue"]
                if self.current_page == page_id
                else theme["text_secondary"]
            )
            table.add_row(f"[{style}]{marker}{icon_name}[/] [dim]({page.lower()})[/]")

        self.console.print(
            Panel(
                table,
                title=f"[{theme['text_muted']}]Navigation[/]",
                style=theme["bg_secondary"],
                border_style=theme["border"],
                width=30,
            )
        )

        return self.current_page

    def render_overview(self):
        """Render overview page"""
        theme = self.theme

        # Metrics
        metrics = Table(show_header=False, box=None, padding=0)
        metrics.add_column()
        metrics.add_column(justify="center")
        metrics.add_column()

        metrics.add_row(
            f"[{theme['accent_blue']}]4[/{theme['accent_blue']}]",
            f"[{theme['accent_green']}]12[/{theme['accent_green']}]",
            f"[{theme['accent_orange']}]3[/{theme['accent_orange']}]",
        )
        metrics.add_row("Active Agents", "Installed Skills", "Active Sessions")

        self.console.print(
            Panel(
                metrics,
                title=f"[{theme['accent_blue']}]// System_Overview[/]",
                style=theme["bg_secondary"],
                border_style=theme["border"],
            )
        )

        # Agents
        agents_table = Table(show_header=True, box=None)
        agents_table.add_column("Agent", style=theme["text_primary"])
        agents_table.add_column("Description", style=theme["text_secondary"])
        agents_table.add_column("Status", style=theme["text_primary"])

        for agent_id, agent in self.agents.items():
            status_color = {
                AgentStatus.ONLINE: theme["accent_green"],
                AgentStatus.RUNNING: theme["accent_blue"],
                AgentStatus.ERROR: theme["accent_red"],
            }.get(agent.status, theme["text_muted"])

            agents_table.add_row(
                f"{agent.icon} {agent.agent_id}",
                agent.description,
                f"[{status_color}]{agent.status.value.upper()}[/{status_color}]",
            )

        self.console.print(
            Panel(
                agents_table,
                title=f"[{theme['accent_blue']}]// Registered_Agents[/]",
                style=theme["bg_secondary"],
                border_style=theme["border"],
            )
        )

    def render_agent_monitor(self):
        """Render agent monitor page"""
        theme = self.theme

        self.console.print(
            f"\n[{theme['accent_blue']}]// Agent_Monitor[/] [dim](Live)[/]\n"
        )

        for agent_id, agent in self.agents.items():
            status_color = {
                AgentStatus.ONLINE: theme["accent_green"],
                AgentStatus.RUNNING: theme["accent_blue"],
                AgentStatus.ERROR: theme["accent_red"],
            }.get(agent.status, theme["text_muted"])

            with self.console.status(
                f"[{status_color}]{agent.status.value.upper()}[/{status_color}]",
                spinner="dots12",
            ):
                pass

            panel_content = Text()
            panel_content.append(f"Status: ", style=theme["text_muted"])
            panel_content.append(f"{agent.status.value.upper()}\n", style=status_color)
            panel_content.append(f"Current Task: ", style=theme["text_muted"])
            panel_content.append(f"{agent.current_task}\n", style=theme["text_primary"])
            panel_content.append(f"Last Update: ", style=theme["text_muted"])
            panel_content.append(
                f"{datetime.fromtimestamp(agent.last_update).strftime('%H:%M:%S')}",
                style=theme["text_secondary"],
            )

            self.console.print(
                Panel(
                    panel_content,
                    title=f"{agent.icon} {agent.agent_id}",
                    style=theme["bg_secondary"],
                    border_style=theme["border"]
                    if agent.status != AgentStatus.RUNNING
                    else status_color,
                )
            )
            self.console.print()

    def render_results(self):
        """Render task results page"""
        theme = self.theme

        self.console.print(f"\n[{theme['accent_blue']}]// Task_Execution_Results[/]\n")

        if not self.task_steps:
            self.console.print(
                Panel(
                    f"[{theme['text_muted']}]No task results yet.[/]",
                    style=theme["bg_secondary"],
                    border_style=theme["border"],
                )
            )
            return

        for i, step in enumerate(self.task_steps):
            status_icon = {
                StepStatus.PENDING: "⏳",
                StepStatus.RUNNING: "🔄",
                StepStatus.COMPLETED: "✅",
                StepStatus.ERROR: "❌",
            }.get(step.status, "⚪")

            status_color = {
                StepStatus.PENDING: theme["text_muted"],
                StepStatus.RUNNING: theme["accent_blue"],
                StepStatus.COMPLETED: theme["accent_green"],
                StepStatus.ERROR: theme["accent_red"],
            }.get(step.status, theme["text_muted"])

            panel_content = Text()
            panel_content.append(f"Instruction: ", style=theme["text_muted"])
            panel_content.append(f"{step.instruction}\n", style=theme["text_primary"])

            if step.result:
                panel_content.append(f"Result:\n", style=theme["text_muted"])
                panel_content.append(
                    f"{step.result[:200]}...", style=theme["accent_green"]
                )

            if step.duration:
                panel_content.append(
                    f"\nDuration: {step.duration:.2f}s", style=theme["text_muted"]
                )

            # Draw connector line if not last step
            connector = "│" if i < len(self.task_steps) - 1 else " "

            self.console.print(
                f"[{status_color}]{status_icon}[/{status_color}] {connector} ", end=""
            )
            self.console.print(
                Panel(
                    panel_content,
                    style=theme["bg_secondary"],
                    border_style=status_color,
                )
            )

            if i < len(self.task_steps) - 1:
                self.console.print(f"[{theme['border']}]  │[/]")

    def render_chat(self):
        """Render chat page"""
        theme = self.theme

        self.console.print(f"\n[{theme['accent_blue']}]// Task_Input[/]\n")

        user_input = Prompt.ask(f"[{theme['accent_blue']}]Enter task[/]").strip()

        if user_input:
            task_id = str(uuid.uuid4())[:8]
            self.current_task_id = task_id

            # Simulate task execution
            steps = [
                ("orchestrator", f"Planning: {user_input[:30]}..."),
                ("research_agent", f"Researching: {user_input[:30]}..."),
                ("executor_agent", f"Executing: {user_input[:30]}..."),
                ("writer_agent", f"Writing summary for: {user_input[:30]}..."),
            ]

            self.console.print(
                f"\n[{theme['accent_blue']}]Executing task {task_id}...[/]\n"
            )

            self.task_steps = []

            for agent_id, instruction in steps:
                step = TaskStep(agent_id, instruction)
                step.status = StepStatus.RUNNING
                step.start_time = time.time()
                self.agents[agent_id].status = AgentStatus.RUNNING
                self.agents[agent_id].current_task = instruction
                self.agents[agent_id].last_update = time.time()

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console,
                ) as progress:
                    progress.add_task(f"Running {agent_id}...", total=None)
                    time.sleep(1)

                step.status = StepStatus.COMPLETED
                step.end_time = time.time()
                step.result = f"Step completed successfully. Processed {len(user_input)} characters."
                self.agents[agent_id].status = AgentStatus.ONLINE
                self.agents[agent_id].current_task = "Idle"
                self.agents[agent_id].last_update = time.time()

                self.task_steps.append(step)

                self.console.print(
                    f"[{theme['accent_green']}]✓[/] {agent_id}: {instruction}"
                )

            self.console.print(
                f"\n[{theme['accent_green']}]✅ Task completed![/] Check results in the Results tab."
            )

            self.messages.append({"role": "user", "content": user_input})
            self.messages.append(
                {
                    "role": "assistant",
                    "content": f"Task {task_id} completed with {len(steps)} steps.",
                }
            )

    def render_providers(self):
        """Render providers page"""
        theme = self.theme

        providers = [
            ("anthropic", "Anthropic", "claude-sonnet-4-5", AgentStatus.ONLINE),
            ("openai", "OpenAI", "gpt-4o", AgentStatus.ONLINE),
        ]

        table = Table(show_header=True, box=None)
        table.add_column("Provider", style=theme["text_primary"])
        table.add_column("Model", style=theme["text_secondary"])
        table.add_column("Status", style=theme["text_primary"])

        for pid, name, model, status in providers:
            status_color = theme["accent_green"]
            table.add_row(
                f"🔌 {name}",
                model,
                f"[{status_color}]{status.value.upper()}[/{status_color}]",
            )

        self.console.print(
            Panel(
                table,
                title=f"[{theme['accent_blue']}]// Model_Providers[/]",
                style=theme["bg_secondary"],
                border_style=theme["border"],
            )
        )

    def render_skills(self):
        """Render skills page"""
        theme = self.theme

        skills = [
            ("shell", "Shell", "Execute shell commands"),
            ("web_search", "Web Search", "Search the web for information"),
            ("summarize", "Summarize", "Summarize text and documents"),
            ("ui-ux-pro-max", "UI/UX Pro Max", "Design intelligence for UI/UX"),
            ("github-code-search", "GitHub Code Search", "Search code on GitHub"),
        ]

        table = Table(show_header=True, box=None)
        table.add_column("Skill", style=theme["text_primary"])
        table.add_column("Description", style=theme["text_secondary"])
        table.add_column("Status", style=theme["text_primary"])

        for sid, name, desc in skills:
            table.add_row(
                f"🧩 {name}",
                desc,
                f"[{theme['accent_green']}]ENABLED[/{theme['accent_green']}]",
            )

        self.console.print(
            Panel(
                table,
                title=f"[{theme['accent_blue']}]// Installed_Skills[/]",
                style=theme["bg_secondary"],
                border_style=theme["border"],
            )
        )

    def render_config(self):
        """Render config page"""
        theme = self.theme

        config_text = Text()
        config_text.append("Version: ", style=theme["text_muted"])
        config_text.append("2.0.0\n", style=theme["text_primary"])
        config_text.append("Environment: ", style=theme["text_muted"])
        config_text.append("Production\n", style=theme["text_primary"])
        config_text.append("Python: ", style=theme["text_muted"])
        config_text.append(f"{sys.version.split()[0]}\n", style=theme["text_primary"])
        config_text.append("Framework: ", style=theme["text_muted"])
        config_text.append("Rich TUI\n", style=theme["text_primary"])
        config_text.append("Database: ", style=theme["text_muted"])
        config_text.append("SQLite\n", style=theme["text_primary"])
        config_text.append("Vector Store: ", style=theme["text_muted"])
        config_text.append("LanceDB", style=theme["text_primary"])

        self.console.print(
            Panel(
                config_text,
                title=f"[{theme['accent_blue']}]// System_Configuration[/]",
                style=theme["bg_secondary"],
                border_style=theme["border"],
            )
        )

    def render_footer(self):
        """Render footer with keyboard hints"""
        theme = self.theme
        self.console.print(
            f"\n[{theme['text_muted']}][1-7] Navigate  |  [t] Toggle Theme  |  [q] Quit[/]"
        )

    def run(self):
        """Main application loop"""
        pages = [
            "overview",
            "monitor",
            "results",
            "chat",
            "providers",
            "skills",
            "config",
        ]
        page_icons = ["🏠", "🤖", "📊", "💬", "🔌", "🧩", "⚙️"]

        while self.running:
            self.clear_screen()
            self.render_header()

            # Navigation
            self.console.print(f"\n[{self.theme['text_muted']}]Navigation:[/]")
            for i, (page, icon) in enumerate(zip(pages, page_icons), 1):
                marker = "▶" if self.current_page == page else " "
                style = (
                    self.theme["accent_blue"]
                    if self.current_page == page
                    else self.theme["text_secondary"]
                )
                self.console.print(
                    f"  [{style}][{i}] {marker} {icon} {page.capitalize()}[/{style}]"
                )

            self.console.print()

            # Render current page
            if self.current_page == "overview":
                self.render_overview()
            elif self.current_page == "monitor":
                self.render_agent_monitor()
            elif self.current_page == "results":
                self.render_results()
            elif self.current_page == "chat":
                self.render_chat()
            elif self.current_page == "providers":
                self.render_providers()
            elif self.current_page == "skills":
                self.render_skills()
            elif self.current_page == "config":
                self.render_config()

            self.render_footer()

            # Read key
            try:
                key = self.console.input("\n> ").strip().lower()

                if key == "q":
                    self.running = False
                    break
                elif key == "t":
                    self.toggle_theme()
                elif key in ["1", "2", "3", "4", "5", "6", "7"]:
                    idx = int(key) - 1
                    if 0 <= idx < len(pages):
                        self.current_page = pages[idx]
                elif key == "" and self.current_page == "chat":
                    self.render_chat()

            except (KeyboardInterrupt, EOFError):
                self.running = False
                break

        self.console.print(f"\n[{self.theme['accent_blue']}]Goodbye![/]")


def main():
    dashboard = MultiAgentDashboard()
    dashboard.run()


if __name__ == "__main__":
    main()
