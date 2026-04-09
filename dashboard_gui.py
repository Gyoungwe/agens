#!/usr/bin/env python3
"""
Multi-Agent Dashboard - Open WebUI Style
Full-featured with multi-agent collaboration and adjustable workflow
"""

import os
import sys
import json
import time
import threading
from datetime import datetime
from typing import Optional, List, Dict

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox

    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    print("Error: tkinter not available")
    sys.exit(1)


class Theme:
    DARK = {
        "bg_app": "#1a1a2e",
        "bg_sidebar": "#16213e",
        "bg_header": "#0f3460",
        "bg_card": "#1f4068",
        "bg_input": "#16213e",
        "bg_chat": "#1a1a2e",
        "bg_user_msg": "#e94560",
        "bg_assistant_msg": "#1f4068",
        "text_primary": "#ffffff",
        "text_secondary": "#a0a0a0",
        "text_muted": "#6b7280",
        "accent": "#e94560",
        "accent_hover": "#c73e54",
        "success": "#22c55e",
        "error": "#ef4444",
        "warning": "#f59e0b",
    }

    LIGHT = {
        "bg_app": "#f8fafc",
        "bg_sidebar": "#f1f5f9",
        "bg_header": "#ffffff",
        "bg_card": "#ffffff",
        "bg_input": "#f1f5f9",
        "bg_chat": "#f8fafc",
        "bg_user_msg": "#3b82f6",
        "bg_assistant_msg": "#e2e8f0",
        "text_primary": "#1e293b",
        "text_secondary": "#64748b",
        "text_muted": "#94a3b8",
        "accent": "#3b82f6",
        "accent_hover": "#2563eb",
        "success": "#22c55e",
        "error": "#ef4444",
        "warning": "#f59e0b",
    }


class MiniMaxClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY")
        self.base_url = "https://api.minimaxi.com/v1"

    def chat(self, messages: list, max_tokens: int = 2048) -> str:
        import urllib.request
        import urllib.error
        import json

        if not self.api_key:
            return "Error: No API key configured."

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": "MiniMax-M2.7",
            "messages": messages,
            "max_tokens": max_tokens,
        }
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
                return (
                    result.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "No response")
                )
        except Exception as e:
            return f"Error: {str(e)}"


class Agent:
    def __init__(self, agent_id: str, name: str, icon: str, desc: str, skills: list):
        self.agent_id = agent_id
        self.name = name
        self.icon = icon
        self.desc = desc
        self.skills = skills
        self.status = "idle"
        self.enabled = True


class MultiAgentDashboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Multi-Agent Dashboard")
        self.root.geometry("1400x900")
        self.root.minsize(1100, 750)

        self.is_dark = True
        self.theme = Theme.DARK

        self.minimax = MiniMaxClient()
        self.messages: List[Dict] = []

        # Define agents with their skills
        self.agents = {
            "orchestrator": Agent(
                "orchestrator",
                "Orchestrator",
                "🎯",
                "Task planning & dispatch",
                ["planning", "coordination", "synthesis"],
            ),
            "research": Agent(
                "research",
                "Research Agent",
                "🔍",
                "Web search & analysis",
                ["web_search", "summarize", "analysis", "fact_check"],
            ),
            "executor": Agent(
                "executor",
                "Executor Agent",
                "⚡",
                "Code execution & tools",
                ["shell", "github", "file_ops", "api_calls"],
            ),
            "writer": Agent(
                "writer",
                "Writer Agent",
                "✍️",
                "Content generation",
                ["format", "translate", "writing", "editing"],
            ),
        }

        # All available skills
        self.all_skills = {
            "planning": {
                "name": "Task Planning",
                "desc": "Break down tasks",
                "agent": "orchestrator",
            },
            "coordination": {
                "name": "Coordination",
                "desc": "Manage workflow",
                "agent": "orchestrator",
            },
            "synthesis": {
                "name": "Synthesis",
                "desc": "Combine results",
                "agent": "orchestrator",
            },
            "web_search": {
                "name": "Web Search",
                "desc": "Search internet",
                "agent": "research",
            },
            "summarize": {
                "name": "Summarize",
                "desc": "Summarize content",
                "agent": "research",
            },
            "analysis": {
                "name": "Analysis",
                "desc": "Data analysis",
                "agent": "research",
            },
            "fact_check": {
                "name": "Fact Check",
                "desc": "Verify facts",
                "agent": "research",
            },
            "shell": {
                "name": "Shell Commands",
                "desc": "Execute commands",
                "agent": "executor",
            },
            "github": {
                "name": "GitHub Operations",
                "desc": "Git operations",
                "agent": "executor",
            },
            "file_ops": {
                "name": "File Operations",
                "desc": "Read/write files",
                "agent": "executor",
            },
            "api_calls": {
                "name": "API Calls",
                "desc": "Make API requests",
                "agent": "executor",
            },
            "format": {
                "name": "Format Output",
                "desc": "Format results",
                "agent": "writer",
            },
            "translate": {
                "name": "Translate",
                "desc": "Translate text",
                "agent": "writer",
            },
            "writing": {
                "name": "Writing",
                "desc": "Generate content",
                "agent": "writer",
            },
            "editing": {"name": "Editing", "desc": "Edit documents", "agent": "writer"},
        }

        # Workflow configuration - adjustable
        self.workflow_steps = [
            {"agent": "orchestrator", "name": "Plan", "enabled": True, "order": 0},
            {"agent": "research", "name": "Research", "enabled": True, "order": 1},
            {"agent": "executor", "name": "Execute", "enabled": True, "order": 2},
            {"agent": "writer", "name": "Write", "enabled": True, "order": 3},
        ]

        self.current_view = tk.StringVar(value="home")

        self._create_widgets()
        self._apply_theme()

    def _create_widgets(self):
        self.main_container = tk.PanedWindow(
            self.root,
            orient=tk.HORIZONTAL,
            sashrelief=tk.FLAT,
            bg=self.theme["bg_sidebar"],
        )
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self._create_sidebar()
        self._create_main_area()
        self._create_statusbar()

    def _create_sidebar(self):
        sidebar = tk.Frame(self.main_container, bg=self.theme["bg_sidebar"], width=280)
        self.main_container.add(sidebar, width=280)

        header = tk.Frame(sidebar, bg=self.theme["bg_sidebar"], height=70)
        header.pack(fill=tk.X, pady=(0, 15))
        header.pack_propagate(False)

        logo_frame = tk.Frame(header, bg=self.theme["bg_sidebar"])
        logo_frame.pack(expand=True)

        tk.Label(
            logo_frame, text="🤖", font=("Consolas", 24), bg=self.theme["bg_sidebar"]
        ).pack(side=tk.LEFT, padx=(15, 10))
        tk.Label(
            logo_frame,
            text="Multi-Agent",
            font=("Consolas", 16, "bold"),
            bg=self.theme["bg_sidebar"],
            fg=self.theme["text_primary"],
        ).pack(side=tk.LEFT)

        # New Chat button
        new_chat_btn = tk.Frame(
            sidebar, bg=self.theme["accent"], cursor="hand2", height=45
        )
        new_chat_btn.pack(fill=tk.X, padx=15, pady=(0, 15))
        new_chat_btn.pack_propagate(False)

        new_chat_inner = tk.Frame(new_chat_btn, bg=self.theme["accent"])
        new_chat_inner.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        tk.Label(
            new_chat_inner,
            text="+  New Chat",
            font=("Consolas", 12, "bold"),
            bg=self.theme["accent"],
            fg="white",
        ).pack()
        new_chat_btn.bind("<Button-1>", lambda e: self.show_chat())

        # Navigation
        nav_items = [
            ("🏠", "Home", "home"),
            ("💬", "Chat Mode", "chat"),
            ("🔄", "Collaboration", "collab"),
            ("🤖", "Agents & Skills", "agents"),
            ("📊", "Monitor", "monitor"),
            ("🔌", "Models", "models"),
            ("📋", "History", "history"),
            ("⚙️", "Settings", "settings"),
        ]

        nav_frame = tk.Frame(sidebar, bg=self.theme["bg_sidebar"])
        nav_frame.pack(fill=tk.BOTH, expand=True, padx=12)

        self.nav_buttons = {}
        for icon, label, view_id in nav_items:
            btn = tk.Frame(nav_frame, bg=self.theme["bg_card"], cursor="hand2")
            btn.pack(fill=tk.X, pady=4)

            btn_inner = tk.Frame(btn, bg=self.theme["bg_card"])
            btn_inner.pack(fill=tk.X, padx=12, pady=8)

            tk.Label(
                btn_inner,
                text=f"{icon}  {label}",
                font=("Consolas", 11),
                bg=self.theme["bg_card"],
                fg=self.theme["text_secondary"],
            ).pack(side=tk.LEFT)

            btn.bind("<Button-1>", lambda e, v=view_id: self.show_view(v))
            btn_inner.bind("<Button-1>", lambda e, v=view_id: self.show_view(v))

            self.nav_buttons[view_id] = btn

        # Theme toggle
        bottom_frame = tk.Frame(sidebar, bg=self.theme["bg_sidebar"], height=50)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)
        bottom_frame.pack_propagate(False)

        theme_btn = tk.Frame(bottom_frame, bg=self.theme["bg_card"], cursor="hand2")
        theme_btn.pack(expand=True, padx=12)

        self.theme_label = tk.Label(
            theme_btn,
            text=f"{'☀️' if self.is_dark else '🌙'}  {'Light' if self.is_dark else 'Dark'} Mode",
            font=("Consolas", 10),
            bg=self.theme["bg_card"],
            fg=self.theme["text_secondary"],
        )
        self.theme_label.pack(expand=True)
        theme_btn.bind("<Button-1>", lambda e: self.toggle_theme())

        self.main_container.add(sidebar, width=280)

    def _create_main_area(self):
        self.content_area = tk.Frame(self.main_container, bg=self.theme["bg_app"])
        self.main_container.add(self.content_area, width=1100)

        self.views = {}

        self.views["home"] = self._create_home_view()
        self.views["chat"] = self._create_chat_view()
        self.views["collab"] = self._create_collab_view()
        self.views["agents"] = self._create_agents_view()
        self.views["monitor"] = self._create_monitor_view()
        self.views["models"] = self._create_models_view()
        self.views["history"] = self._create_history_view()
        self.views["settings"] = self._create_settings_view()

        self.show_view("home")

    def _create_home_view(self):
        frame = tk.Frame(self.content_area, bg=self.theme["bg_app"])

        header = tk.Frame(frame, bg=self.theme["bg_app"], height=100)
        header.pack(fill=tk.X, pady=(30, 20))
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Multi-Agent Dashboard",
            font=("Consolas", 26, "bold"),
            bg=self.theme["bg_app"],
            fg=self.theme["text_primary"],
        ).pack(anchor="w", padx=40, pady=(30, 5))
        tk.Label(
            header,
            text="AI-powered multi-agent orchestration system",
            font=("Consolas", 13),
            bg=self.theme["bg_app"],
            fg=self.theme["text_secondary"],
        ).pack(anchor="w", padx=40)

        stats_frame = tk.Frame(frame, bg=self.theme["bg_app"])
        stats_frame.pack(fill=tk.X, padx=40, pady=20)

        stats = [
            ("🤖", "4", "Active Agents"),
            ("🧩", "15", "Total Skills"),
            ("💬", "12", "Total Chats"),
            ("📊", "100%", "Success Rate"),
        ]

        for i, (icon, value, label) in enumerate(stats):
            card = tk.Frame(stats_frame, bg=self.theme["bg_card"])
            card.grid(row=0, column=i, padx=10, sticky="nsew")

            tk.Label(
                card, text=icon, font=("Consolas", 24), bg=self.theme["bg_card"]
            ).pack(pady=(20, 10))
            tk.Label(
                card,
                text=value,
                font=("Consolas", 28, "bold"),
                bg=self.theme["bg_card"],
                fg=self.theme["accent"],
            ).pack()
            tk.Label(
                card,
                text=label,
                font=("Consolas", 11),
                bg=self.theme["bg_card"],
                fg=self.theme["text_secondary"],
            ).pack(pady=(5, 20))

        stats_frame.columnconfigure(0, weight=1)
        stats_frame.columnconfigure(1, weight=1)
        stats_frame.columnconfigure(2, weight=1)
        stats_frame.columnconfigure(3, weight=1)

        actions_label = tk.Label(
            frame,
            text="Quick Actions",
            font=("Consolas", 16, "bold"),
            bg=self.theme["bg_app"],
            fg=self.theme["text_primary"],
        )
        actions_label.pack(anchor="w", padx=40, pady=(20, 10))

        actions_frame = tk.Frame(frame, bg=self.theme["bg_app"])
        actions_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)

        actions = [
            ("💬", "Chat Mode", "Simple chat", lambda: self.show_view("chat")),
            (
                "🔄",
                "Collaboration",
                "Multi-agent workflow",
                lambda: self.show_view("collab"),
            ),
            (
                "🤖",
                "Agents & Skills",
                "Manage agents",
                lambda: self.show_view("agents"),
            ),
            ("📊", "Monitor", "View status", lambda: self.show_view("monitor")),
        ]

        for i, (icon, title, desc, cmd) in enumerate(actions):
            card = tk.Frame(
                actions_frame, bg=self.theme["bg_card"], cursor="hand2", height=100
            )
            card.grid(row=i // 2, column=i % 2, padx=10, pady=10, sticky="nsew")
            card.pack_propagate(False)

            card_inner = tk.Frame(card, bg=self.theme["bg_card"])
            card_inner.pack(expand=True)

            tk.Label(
                card_inner, text=icon, font=("Consolas", 28), bg=self.theme["bg_card"]
            ).pack(pady=(15, 5))
            tk.Label(
                card_inner,
                text=title,
                font=("Consolas", 13, "bold"),
                bg=self.theme["bg_card"],
                fg=self.theme["text_primary"],
            ).pack()
            tk.Label(
                card_inner,
                text=desc,
                font=("Consolas", 10),
                bg=self.theme["bg_card"],
                fg=self.theme["text_secondary"],
            ).pack(pady=(3, 10))

            for w in [card, card_inner]:
                w.bind("<Button-1>", lambda e, f=cmd: f())

        actions_frame.columnconfigure(0, weight=1)
        actions_frame.columnconfigure(1, weight=1)

        return frame

    def _create_chat_view(self):
        frame = tk.Frame(self.content_area, bg=self.theme["bg_chat"])

        header = tk.Frame(frame, bg=self.theme["bg_header"], height=55)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="💬  Chat Mode",
            font=("Consolas", 14, "bold"),
            bg=self.theme["bg_header"],
            fg=self.theme["text_primary"],
        ).pack(side=tk.LEFT, padx=20, pady=15)

        tk.Button(
            header,
            text="🗑️ Clear",
            font=("Consolas", 10),
            bg=self.theme["bg_header"],
            fg=self.theme["text_secondary"],
            relief=tk.FLAT,
            cursor="hand2",
            command=self.clear_chat,
        ).pack(side=tk.RIGHT, padx=15)

        self.chat_canvas = tk.Canvas(
            frame, bg=self.theme["bg_chat"], highlightthickness=0
        )
        self.chat_scrollbar = ttk.Scrollbar(
            frame, orient=tk.VERTICAL, command=self.chat_canvas.yview
        )
        self.chat_messages = tk.Frame(self.chat_canvas, bg=self.theme["bg_chat"])

        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)
        self.chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.chat_window_id = self.chat_canvas.create_window(
            (0, 0), window=self.chat_messages, anchor="nw", width=1050
        )

        self.chat_messages.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(
                scrollregion=self.chat_canvas.bbox("all")
            ),
        )
        self.chat_canvas.bind(
            "<Configure>",
            lambda e: self.chat_canvas.itemconfig(self.chat_window_id, width=e.width),
        )

        input_frame = tk.Frame(frame, bg=self.theme["bg_header"], height=80)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        input_frame.pack_propagate(False)

        input_inner = tk.Frame(input_frame, bg=self.theme["bg_input"], padx=20, pady=12)
        input_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.chat_input = tk.Entry(
            input_inner,
            font=("Consolas", 13),
            bg=self.theme["bg_input"],
            fg=self.theme["text_primary"],
            insertbackground=self.theme["text_primary"],
            relief=tk.FLAT,
        )
        self.chat_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, ipady=10)
        self.chat_input.bind("<Return>", lambda e: self.send_chat())

        send_btn = tk.Frame(
            input_inner, bg=self.theme["accent"], cursor="hand2", width=50, height=40
        )
        send_btn.pack(side=tk.RIGHT, padx=(10, 0))
        send_btn.pack_propagate(False)

        tk.Label(
            send_btn,
            text="➤",
            font=("Consolas", 18),
            bg=self.theme["accent"],
            fg="white",
        ).place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        send_btn.bind("<Button-1>", lambda e: self.send_chat())

        return frame

    def _create_collab_view(self):
        """Collaboration Mode with adjustable workflow and skill permissions"""
        frame = tk.Frame(self.content_area, bg=self.theme["bg_app"])

        header = tk.Frame(frame, bg=self.theme["bg_app"], height=70)
        header.pack(fill=tk.X, pady=(20, 10))
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🔄  Collaboration Mode",
            font=("Consolas", 20, "bold"),
            bg=self.theme["bg_app"],
            fg=self.theme["text_primary"],
        ).pack(anchor="w", padx=40, pady=20)

        # Main content
        main_frame = tk.Frame(frame, bg=self.theme["bg_app"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)

        # Left - Task Input + Workflow Config
        left_frame = tk.Frame(main_frame, bg=self.theme["bg_app"])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 20))

        # Task Input
        tk.Label(
            left_frame,
            text="Enter Task:",
            font=("Consolas", 12, "bold"),
            bg=self.theme["bg_app"],
            fg=self.theme["text_primary"],
        ).pack(anchor="w", pady=(0, 10))

        self.collab_input = tk.Text(
            left_frame,
            font=("Consolas", 11),
            bg=self.theme["bg_input"],
            fg=self.theme["text_primary"],
            insertbackground=self.theme["text_primary"],
            relief=tk.FLAT,
            height=6,
            wrap=tk.WORD,
        )
        self.collab_input.pack(fill=tk.X, pady=(0, 10))

        # Execute button
        exec_btn = tk.Frame(
            left_frame, bg=self.theme["accent"], cursor="hand2", height=45
        )
        exec_btn.pack(fill=tk.X, pady=(0, 15))
        exec_btn.pack_propagate(False)

        tk.Label(
            exec_btn,
            text="🚀 Execute Workflow",
            font=("Consolas", 12, "bold"),
            bg=self.theme["accent"],
            fg="white",
        ).place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        exec_btn.bind("<Button-1>", lambda e: self.execute_workflow())

        # Workflow Configuration
        tk.Label(
            left_frame,
            text="Workflow Configuration:",
            font=("Consolas", 12, "bold"),
            bg=self.theme["bg_app"],
            fg=self.theme["text_primary"],
        ).pack(anchor="w", pady=(10, 10))

        workflow_card = tk.Frame(left_frame, bg=self.theme["bg_card"])
        workflow_card.pack(fill=tk.X, pady=(0, 10))

        self.workflow_checkboxes = {}
        for step in self.workflow_steps:
            row = tk.Frame(workflow_card, bg=self.theme["bg_card"])
            row.pack(fill=tk.X, padx=10, pady=5)

            var = tk.BooleanVar(value=step["enabled"])
            self.workflow_checkboxes[step["agent"]] = var

            cb = tk.Checkbutton(
                row,
                variable=var,
                bg=self.theme["bg_card"],
                activebackground=self.theme["bg_card"],
                font=("Consolas", 11),
                selectcolor=self.theme["bg_card"],
            )
            cb.pack(side=tk.LEFT)

            agent = self.agents.get(step["agent"])
            icon = agent.icon if agent else "❓"
            tk.Label(
                row,
                text=f"{icon} {step['name']}",
                font=("Consolas", 11),
                bg=self.theme["bg_card"],
                fg=self.theme["text_primary"],
            ).pack(side=tk.LEFT, padx=5)

            # Skills for this agent
            if agent:
                skills_text = ", ".join(agent.skills[:3])
                tk.Label(
                    row,
                    text=f"({skills_text})",
                    font=("Consolas", 9),
                    bg=self.theme["bg_card"],
                    fg=self.theme["text_muted"],
                ).pack(side=tk.RIGHT)

        # Right - Results
        right_frame = tk.Frame(main_frame, bg=self.theme["bg_app"])
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(
            right_frame,
            text="Workflow Results:",
            font=("Consolas", 12, "bold"),
            bg=self.theme["bg_app"],
            fg=self.theme["text_primary"],
        ).pack(anchor="w", pady=(0, 10))

        # Results notebook
        self.results_notebook = ttk.Notebook(right_frame)
        self.results_notebook.pack(fill=tk.BOTH, expand=True)

        self.agent_results = {}
        for agent_id, agent in self.agents.items():
            tab = tk.Frame(self.results_notebook, bg=self.theme["bg_card"])
            self.results_notebook.add(tab, text=f"{agent.icon} {agent.name}")

            # Agent skills header
            skills_header = tk.Frame(tab, bg=self.theme["bg_header"])
            skills_header.pack(fill=tk.X, padx=5, pady=5)

            tk.Label(
                skills_header,
                text=f"Skills: {', '.join(agent.skills)}",
                font=("Consolas", 9),
                bg=self.theme["bg_header"],
                fg=self.theme["text_secondary"],
            ).pack(anchor="w", padx=5)

            result_text = scrolledtext.ScrolledText(
                tab,
                font=("Consolas", 10),
                bg=self.theme["bg_card"],
                fg=self.theme["text_primary"],
                wrap=tk.WORD,
            )
            result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            self.agent_results[agent_id] = result_text

        return frame

    def _create_agents_view(self):
        """Agents & Skills management with permissions"""
        frame = tk.Frame(self.content_area, bg=self.theme["bg_app"])

        header = tk.Frame(frame, bg=self.theme["bg_app"], height=70)
        header.pack(fill=tk.X, pady=(20, 10))
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🤖  Agents & Skills",
            font=("Consolas", 20, "bold"),
            bg=self.theme["bg_app"],
            fg=self.theme["text_primary"],
        ).pack(anchor="w", padx=40, pady=20)

        # Main content - Agent cards with skills
        content_frame = tk.Frame(frame, bg=self.theme["bg_app"])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)

        for agent_id, agent in self.agents.items():
            # Agent card
            card = tk.Frame(content_frame, bg=self.theme["bg_card"])
            card.pack(fill=tk.X, pady=8)

            # Agent header
            header_row = tk.Frame(card, bg=self.theme["bg_card"])
            header_row.pack(fill=tk.X, padx=15, pady=10)

            tk.Label(
                header_row,
                text=agent.icon,
                font=("Consolas", 28),
                bg=self.theme["bg_card"],
            ).pack(side=tk.LEFT, padx=(0, 15))

            info_frame = tk.Frame(header_row, bg=self.theme["bg_card"])
            info_frame.pack(side=tk.LEFT)

            tk.Label(
                info_frame,
                text=agent.name,
                font=("Consolas", 14, "bold"),
                bg=self.theme["bg_card"],
                fg=self.theme["text_primary"],
            ).pack(anchor="w")
            tk.Label(
                info_frame,
                text=agent.desc,
                font=("Consolas", 11),
                bg=self.theme["bg_card"],
                fg=self.theme["text_secondary"],
            ).pack(anchor="w", pady=(3, 0))

            # Enable/Disable toggle
            var = tk.BooleanVar(value=agent.enabled)
            self.agent_enabled_vars = getattr(self, "agent_enabled_vars", {})
            self.agent_enabled_vars[agent_id] = var

            toggle_btn = tk.Checkbutton(
                header_row,
                variable=var,
                bg=self.theme["bg_card"],
                activebackground=self.theme["bg_card"],
                text="Enabled" if agent.enabled else "Disabled",
                font=("Consolas", 10),
                selectcolor=self.theme["success"],
            )
            toggle_btn.pack(side=tk.RIGHT)

            # Skills section
            skills_frame = tk.Frame(card, bg=self.theme["bg_header"])
            skills_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

            tk.Label(
                skills_frame,
                text="Assigned Skills:",
                font=("Consolas", 10, "bold"),
                bg=self.theme["bg_header"],
                fg=self.theme["text_primary"],
            ).pack(anchor="w", pady=(8, 5))

            # Skills grid
            skills_grid = tk.Frame(skills_frame, bg=self.theme["bg_header"])
            skills_grid.pack(fill=tk.X, pady=(0, 8))

            for skill_id in agent.skills:
                skill = self.all_skills.get(skill_id, {})
                skill_chip = tk.Frame(
                    skills_grid, bg=self.theme["accent"], cursor="hand2", padx=8, pady=3
                )
                skill_chip.pack(side=tk.LEFT, padx=3, pady=3)

                tk.Label(
                    skill_chip,
                    text=f"{skill.get('name', skill_id)}",
                    font=("Consolas", 9),
                    bg=self.theme["accent"],
                    fg="white",
                ).pack()

                # Right-click to remove
                def remove_skill(event, aid=agent_id, sid=skill_id):
                    self.remove_skill_from_agent(aid, sid)

                skill_chip.bind("<Button-3>", remove_skill)

            # Add skill button
            add_btn = tk.Frame(
                skills_grid, bg=self.theme["bg_card"], cursor="hand2", padx=8, pady=3
            )
            add_btn.pack(side=tk.LEFT, padx=3, pady=3)

            tk.Label(
                add_btn,
                text="+ Add",
                font=("Consolas", 9),
                bg=self.theme["bg_card"],
                fg=self.theme["text_muted"],
            ).pack()
            add_btn.bind(
                "<Button-1>", lambda e, aid=agent_id: self.show_add_skill_dialog(aid)
            )

        content_frame.columnconfigure(0, weight=1)

        return frame

    def _create_monitor_view(self):
        frame = tk.Frame(self.content_area, bg=self.theme["bg_app"])

        header = tk.Frame(frame, bg=self.theme["bg_app"], height=70)
        header.pack(fill=tk.X, pady=(20, 10))
        header.pack_propagate(False)

        tk.Label(
            header,
            text="📊  Agent Monitor",
            font=("Consolas", 20, "bold"),
            bg=self.theme["bg_app"],
            fg=self.theme["text_primary"],
        ).pack(anchor="w", padx=40, pady=20)

        stats_frame = tk.Frame(frame, bg=self.theme["bg_app"])
        stats_frame.pack(fill=tk.X, padx=40, pady=(0, 20))

        stats = [
            ("Total Tasks", "156"),
            ("Running", "0"),
            ("Completed", "154"),
            ("Failed", "2"),
        ]
        for label, value in stats:
            stat_card = tk.Frame(stats_frame, bg=self.theme["bg_card"])
            stat_card.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)

            tk.Label(
                stat_card,
                text=value,
                font=("Consolas", 24, "bold"),
                bg=self.theme["bg_card"],
                fg=self.theme["accent"],
            ).pack(pady=(15, 5))
            tk.Label(
                stat_card,
                text=label,
                font=("Consolas", 10),
                bg=self.theme["bg_card"],
                fg=self.theme["text_secondary"],
            ).pack(pady=(0, 15))

        monitor_frame = tk.Frame(frame, bg=self.theme["bg_app"])
        monitor_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)

        for agent_id, agent in self.agents.items():
            card = tk.Frame(monitor_frame, bg=self.theme["bg_card"])
            card.pack(fill=tk.X, pady=6)

            tk.Label(
                card, text=agent.icon, font=("Consolas", 24), bg=self.theme["bg_card"]
            ).pack(side=tk.LEFT, padx=20, pady=15)

            info_frame = tk.Frame(card, bg=self.theme["bg_card"])
            info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            tk.Label(
                info_frame,
                text=agent.name,
                font=("Consolas", 13, "bold"),
                bg=self.theme["bg_card"],
                fg=self.theme["text_primary"],
            ).pack(anchor="w")
            tk.Label(
                info_frame,
                text=f"Status: {agent.status} | Tasks: 0 | Skills: {len(agent.skills)}",
                font=("Consolas", 10),
                bg=self.theme["bg_card"],
                fg=self.theme["text_secondary"],
            ).pack(anchor="w", pady=(3, 0))

            tk.Button(
                card,
                text="🔄 Refresh",
                font=("Consolas", 10),
                bg=self.theme["bg_card"],
                fg=self.theme["text_secondary"],
                relief=tk.FLAT,
                cursor="hand2",
                command=lambda a=agent_id: self.refresh_agent(a),
            ).pack(side=tk.RIGHT, padx=20)

        monitor_frame.columnconfigure(0, weight=1)

        return frame

    def _create_models_view(self):
        frame = tk.Frame(self.content_area, bg=self.theme["bg_app"])

        header = tk.Frame(frame, bg=self.theme["bg_app"], height=70)
        header.pack(fill=tk.X, pady=(20, 10))
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🔌  AI Models",
            font=("Consolas", 20, "bold"),
            bg=self.theme["bg_app"],
            fg=self.theme["text_primary"],
        ).pack(anchor="w", padx=40, pady=20)

        models_frame = tk.Frame(frame, bg=self.theme["bg_app"])
        models_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)

        models = [
            ("🔌", "MiniMax M2.7", "MiniMax", "active", False),
            ("🤖", "Claude Sonnet (Config)", "Anthropic", "inactive", True),
            ("💬", "GPT-4o (Config)", "OpenAI", "inactive", True),
        ]

        for icon, name, provider, status, configurable in models:
            card = tk.Frame(models_frame, bg=self.theme["bg_card"])
            card.pack(fill=tk.X, pady=8)

            left = tk.Frame(card, bg=self.theme["bg_card"])
            left.pack(side=tk.LEFT, padx=20, pady=15)

            tk.Label(
                left,
                text=f"{icon} {name}",
                font=("Consolas", 14, "bold"),
                bg=self.theme["bg_card"],
                fg=self.theme["text_primary"],
            ).pack(anchor="w")
            tk.Label(
                left,
                text=f"Provider: {provider}",
                font=("Consolas", 11),
                bg=self.theme["bg_card"],
                fg=self.theme["text_secondary"],
            ).pack(anchor="w", pady=(3, 0))

            right = tk.Frame(card, bg=self.theme["bg_card"])
            right.pack(side=tk.RIGHT, padx=20, pady=15)

            status_color = (
                self.theme["success"]
                if status == "active"
                else self.theme["text_muted"]
            )
            tk.Label(
                right,
                text=f"● {status.upper()}",
                font=("Consolas", 11, "bold"),
                bg=self.theme["bg_card"],
                fg=status_color,
            ).pack(anchor=tk.E)

            if configurable:
                tk.Button(
                    right,
                    text="Configure",
                    font=("Consolas", 10),
                    bg=self.theme["accent"],
                    fg="white",
                    relief=tk.FLAT,
                    cursor="hand2",
                    command=lambda m=name: self.configure_model(m),
                ).pack(pady=(5, 0))

        add_btn = tk.Frame(
            models_frame, bg=self.theme["accent"], cursor="hand2", height=50
        )
        add_btn.pack(fill=tk.X, pady=15)
        add_btn.pack_propagate(False)

        tk.Label(
            add_btn,
            text="+ Add New Model",
            font=("Consolas", 12, "bold"),
            bg=self.theme["accent"],
            fg="white",
        ).place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        add_btn.bind("<Button-1>", lambda e: self.add_model())

        return frame

    def _create_history_view(self):
        frame = tk.Frame(self.content_area, bg=self.theme["bg_app"])

        header = tk.Frame(frame, bg=self.theme["bg_app"], height=70)
        header.pack(fill=tk.X, pady=(20, 10))
        header.pack_propagate(False)

        tk.Label(
            header,
            text="📋  Chat History",
            font=("Consolas", 20, "bold"),
            bg=self.theme["bg_app"],
            fg=self.theme["text_primary"],
        ).pack(anchor="w", padx=40, pady=20)

        history_frame = tk.Frame(frame, bg=self.theme["bg_app"])
        history_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)

        history_items = [
            ("Research latest AI developments", "2024-04-09 00:45", "✅"),
            ("Write Python script for automation", "2024-04-08 22:30", "✅"),
            ("Explain quantum computing", "2024-04-08 20:15", "✅"),
            ("Build landing page for SaaS", "2024-04-07 18:00", "✅"),
        ]

        for title, time_str, status in history_items:
            card = tk.Frame(history_frame, bg=self.theme["bg_card"], cursor="hand2")
            card.pack(fill=tk.X, pady=5)

            tk.Label(
                card,
                text=f"{status} {title}",
                font=("Consolas", 12),
                bg=self.theme["bg_card"],
                fg=self.theme["text_primary"],
            ).pack(side=tk.LEFT, padx=20, pady=12)
            tk.Label(
                card,
                text=time_str,
                font=("Consolas", 10),
                bg=self.theme["bg_card"],
                fg=self.theme["text_muted"],
            ).pack(side=tk.RIGHT, padx=20)

            card.bind("<Button-1>", lambda e, t=title: self.load_chat(t))

        return frame

    def _create_settings_view(self):
        frame = tk.Frame(self.content_area, bg=self.theme["bg_app"])

        header = tk.Frame(frame, bg=self.theme["bg_app"], height=70)
        header.pack(fill=tk.X, pady=(20, 10))
        header.pack_propagate(False)

        tk.Label(
            header,
            text="⚙️  Settings",
            font=("Consolas", 20, "bold"),
            bg=self.theme["bg_app"],
            fg=self.theme["text_primary"],
        ).pack(anchor="w", padx=40, pady=20)

        settings_frame = tk.Frame(frame, bg=self.theme["bg_app"])
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)

        # API Settings
        api_card = tk.LabelFrame(
            settings_frame,
            text=" API Configuration ",
            font=("Consolas", 12, "bold"),
            bg=self.theme["bg_card"],
            fg=self.theme["text_primary"],
            padx=15,
            pady=15,
        )
        api_card.pack(fill=tk.X, pady=10)

        tk.Label(
            api_card,
            text="MiniMax API Key:",
            font=("Consolas", 11),
            bg=self.theme["bg_card"],
            fg=self.theme["text_secondary"],
        ).pack(anchor="w")

        api_key_entry = tk.Entry(
            api_card,
            font=("Consolas", 11),
            bg=self.theme["bg_input"],
            fg=self.theme["text_primary"],
            insertbackground=self.theme["text_primary"],
        )
        api_key_entry.insert(
            0, "sk-cp-****************************" if self.minimax.api_key else ""
        )
        api_key_entry.pack(fill=tk.X, pady=(5, 10))

        tk.Button(
            api_card,
            text="Save API Key",
            font=("Consolas", 10),
            bg=self.theme["accent"],
            fg="white",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: messagebox.showinfo("Save", "API Key saved!"),
        ).pack(anchor="e")

        # Theme
        theme_card = tk.LabelFrame(
            settings_frame,
            text=" Appearance ",
            font=("Consolas", 12, "bold"),
            bg=self.theme["bg_card"],
            fg=self.theme["text_primary"],
            padx=15,
            pady=15,
        )
        theme_card.pack(fill=tk.X, pady=10)

        theme_row = tk.Frame(theme_card, bg=self.theme["bg_card"])
        theme_row.pack(fill=tk.X)

        tk.Label(
            theme_row,
            text="Theme Mode:",
            font=("Consolas", 11),
            bg=self.theme["bg_card"],
            fg=self.theme["text_secondary"],
        ).pack(side=tk.LEFT)

        tk.Button(
            theme_row,
            text=f"{'☀️ Light' if self.is_dark else '🌙 Dark'} Mode",
            font=("Consolas", 10),
            bg=self.theme["accent"],
            fg="white",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.toggle_theme,
        ).pack(side=tk.RIGHT)

        # About
        about_card = tk.LabelFrame(
            settings_frame,
            text=" About ",
            font=("Consolas", 12, "bold"),
            bg=self.theme["bg_card"],
            fg=self.theme["text_primary"],
            padx=15,
            pady=15,
        )
        about_card.pack(fill=tk.X, pady=10)

        about_text = "Version: 2.0.0\nFramework: Multi-Agent Orchestration\nUI: Custom Tkinter (Open WebUI Style)"
        tk.Label(
            about_card,
            text=about_text,
            font=("Consolas", 10),
            bg=self.theme["bg_card"],
            fg=self.theme["text_secondary"],
            justify=tk.LEFT,
        ).pack(anchor="w")

        return frame

    def _create_statusbar(self):
        self.statusbar = tk.Frame(self.root, height=28, bg=self.theme["bg_header"])
        self.statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        self.statusbar.pack_propagate(False)

        self.status_label = tk.Label(
            self.statusbar,
            text="Ready",
            anchor="w",
            font=("Consolas", 10),
            bg=self.theme["bg_header"],
            fg=self.theme["text_muted"],
        )
        self.status_label.pack(side=tk.LEFT, padx=15, pady=4)

        tk.Label(
            self.statusbar,
            text="MiniMax M2.7 | Consolas Font",
            anchor="e",
            font=("Consolas", 10),
            bg=self.theme["bg_header"],
            fg=self.theme["text_muted"],
        ).pack(side=tk.RIGHT, padx=15)

    def _apply_theme(self):
        t = self.theme

        self.root.configure(bg=t["bg_app"])

        for view_id, btn in self.nav_buttons.items():
            if view_id == self.current_view.get():
                btn.configure(bg=t["accent"])
                for child in btn.winfo_children():
                    child.configure(bg=t["accent"])
                    if hasattr(child, "configure"):
                        try:
                            child.configure(fg="white")
                        except:
                            pass
            else:
                btn.configure(bg=t["bg_card"])
                for child in btn.winfo_children():
                    child.configure(bg=t["bg_card"])
                    if hasattr(child, "configure"):
                        try:
                            child.configure(fg=t["text_secondary"])
                        except:
                            pass

        if hasattr(self, "theme_label"):
            self.theme_label.configure(
                text=f"{'☀️' if self.is_dark else '🌙'}  {'Light' if self.is_dark else 'Dark'} Mode",
                bg=t["bg_card"],
                fg=t["text_secondary"],
            )

        if hasattr(self, "statusbar"):
            self.statusbar.configure(bg=t["bg_header"])
            self.status_label.configure(bg=t["bg_header"], fg=t["text_muted"])

    def show_view(self, view_id: str):
        for v in self.views.values():
            v.pack_forget()

        self.views[view_id].pack(fill=tk.BOTH, expand=True)
        self.current_view.set(view_id)
        self._apply_theme()

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        self.theme = Theme.DARK if self.is_dark else Theme.LIGHT
        self._apply_theme()
        self.show_view(self.current_view.get())

    def send_chat(self):
        text = self.chat_input.get().strip()
        if not text:
            return

        self.chat_input.delete(0, tk.END)

        self._add_message(text, is_user=True)
        self.messages.append({"role": "user", "content": text})

        self.status_label.configure(text="MiniMax is thinking...")

        def api_call():
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": text},
            ]
            result = self.minimax.chat(messages)
            self.root.after(0, lambda r=result: self._add_message(r, is_user=False))

        threading.Thread(target=api_call, daemon=True).start()

    def _add_message(self, text: str, is_user: bool):
        bubble = tk.Frame(
            self.chat_messages,
            bg=self.theme["bg_user_msg"] if is_user else self.theme["bg_assistant_msg"],
        )
        bubble.pack(anchor="e" if is_user else "w", pady=5, padx=10, fill=tk.X)

        label = tk.Label(
            bubble,
            text=text,
            font=("Consolas", 11),
            bg=bubble.cget("bg"),
            fg="white" if is_user else self.theme["text_primary"],
            wraplength=700,
            justify="left" if not is_user else "right",
            padx=15,
            pady=10,
        )
        label.pack()

        time_label = tk.Label(
            bubble,
            text=datetime.now().strftime("%H:%M"),
            font=("Consolas", 8),
            bg=bubble.cget("bg"),
            fg=self.theme["text_muted"],
        )
        time_label.pack(anchor="e" if is_user else "w", padx=15, pady=(0, 5))

        if not is_user:
            self.messages.append({"role": "assistant", "content": text})
            self.status_label.configure(text="Ready")

        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    def clear_chat(self):
        for widget in self.chat_messages.winfo_children():
            widget.destroy()
        self.messages = []

    def show_chat(self):
        self.show_view("chat")

    def execute_workflow(self):
        task = self.collab_input.get("1.0", tk.END).strip()
        if not task:
            messagebox.showwarning("Warning", "Please enter a task")
            return

        # Get enabled workflow steps
        enabled_steps = [
            s
            for s in self.workflow_steps
            if self.workflow_checkboxes.get(s["agent"], tk.BooleanVar(value=True)).get()
        ]

        if not enabled_steps:
            messagebox.showwarning(
                "Warning", "Please enable at least one agent in the workflow"
            )
            return

        self.status_label.configure(text="Executing multi-agent workflow...")

        # Clear previous results
        for agent_id, text_widget in self.agent_results.items():
            text_widget.delete("1.0", tk.END)
            text_widget.insert("1.0", "Initializing...")

        def run_workflow():
            try:
                results = {}

                for step in enabled_steps:
                    agent_id = step["agent"]
                    agent = self.agents.get(agent_id)
                    if not agent:
                        continue

                    self.root.after(
                        0,
                        lambda aid=agent_id, txt=f"🔄 {agent.name} is working...": (
                            self._update_agent_result(aid, txt)
                        ),
                    )

                    # Build context from previous results
                    context = f"Original Task: {task}\n\n"
                    for prev_agent_id, prev_result in results.items():
                        context += f"[{prev_agent_id.upper()}]:\n{prev_result}\n\n"

                    # Generate prompt for this agent
                    system_prompt = f"You are {agent.name}. {agent.desc}. Your skills: {', '.join(agent.skills)}."

                    result = self.minimax.chat(
                        [
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user",
                                "content": f"Complete your task based on:\n{context}",
                            },
                        ]
                    )

                    results[agent_id] = result
                    self.root.after(
                        0,
                        lambda aid=agent_id, r=result: self._update_agent_result(
                            aid, r
                        ),
                    )

                self.root.after(
                    0, lambda: self.status_label.configure(text="Workflow completed!")
                )

            except Exception as e:
                self.root.after(
                    0, lambda: self.status_label.configure(text=f"Error: {str(e)}")
                )

        threading.Thread(target=run_workflow, daemon=True).start()

    def _update_agent_result(self, agent_id: str, text: str):
        if agent_id in self.agent_results:
            self.agent_results[agent_id].delete("1.0", tk.END)
            self.agent_results[agent_id].insert("1.0", text)

    # Action handlers
    def refresh_agent(self, agent_id: str):
        self.status_label.configure(text=f"Refreshed {agent_id}")

    def configure_model(self, model: str):
        messagebox.showinfo("Configure", f"Configure {model}")

    def add_model(self):
        messagebox.showinfo("Add Model", "Add new model dialog")

    def remove_skill_from_agent(self, agent_id: str, skill_id: str):
        messagebox.showinfo("Remove Skill", f"Remove {skill_id} from {agent_id}")

    def show_add_skill_dialog(self, agent_id: str):
        # Simple dialog to add skill
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Skill")
        dialog.geometry("400x300")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"Add skill to {agent_id}:", font=("Consolas", 12)).pack(
            pady=10
        )

        # List available skills not already assigned
        agent = self.agents.get(agent_id)
        available = [s for s in self.all_skills.keys() if s not in agent.skills]

        for skill_id in available:
            skill = self.all_skills.get(skill_id, {})
            btn = tk.Button(
                dialog,
                text=f"{skill.get('name', skill_id)} - {skill.get('desc', '')}",
                font=("Consolas", 10),
                command=lambda sid=skill_id: self.add_skill_to_agent(
                    agent_id, sid, dialog
                ),
            )
            btn.pack(fill=tk.X, padx=20, pady=5)

        tk.Button(
            dialog, text="Cancel", font=("Consolas", 10), command=dialog.destroy
        ).pack(pady=10)

    def add_skill_to_agent(self, agent_id: str, skill_id: str, dialog: tk.Toplevel):
        agent = self.agents.get(agent_id)
        if agent and skill_id not in agent.skills:
            skill = self.all_skills.get(skill_id, {})
            agent.skills.append(skill_id)
        dialog.destroy()
        self.show_view("agents")

    def load_chat(self, title: str):
        messagebox.showinfo("Load Chat", f"Loading: {title}")

    def run(self):
        self.root.mainloop()


def main():
    app = MultiAgentDashboard()
    app.run()


if __name__ == "__main__":
    main()
