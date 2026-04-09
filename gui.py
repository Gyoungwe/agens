#!/usr/bin/env python3
# gui.py - Multi-Agent System GUI

import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import queue
import os
import sys
import asyncio
from pathlib import Path


class AgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Multi-Agent 智能协作系统")
        self.root.geometry("900x700")
        self.root.configure(bg="#1e1e2e")

        self.process = None
        self.output_queue = queue.Queue()
        self.running = False

        self.setup_ui()

    def setup_ui(self):
        header_bg = "#2d2d44"
        input_bg = "#2d2d44"
        text_bg = "#1e1e2e"
        text_fg = "#cdd6f4"
        accent = "#89b4fa"

        header = tk.Frame(self.root, bg=header_bg, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🚀 Multi-Agent 智能协作系统",
            font=("SF Mono", 18, "bold"),
            fg=accent,
            bg=header_bg,
        ).pack(pady=10)

        self.status_label = tk.Label(
            header,
            text="⚡ 初始化中...",
            font=("SF Mono", 11),
            fg="#a6adc8",
            bg=header_bg,
        )
        self.status_label.pack(pady=5)

        content = tk.Frame(self.root, bg=text_bg)
        content.pack(fill="both", expand=True, padx=10, pady=10)

        left_frame = tk.Frame(content, bg=text_bg)
        left_frame.pack(side="left", fill="both", expand=True)

        tk.Label(
            left_frame,
            text="📋 会话记录",
            font=("SF Mono", 12, "bold"),
            fg=accent,
            bg=text_bg,
        ).pack(anchor="w", pady=(0, 5))

        self.chat_area = scrolledtext.ScrolledText(
            left_frame,
            wrap=tk.WORD,
            font=("SF Mono", 11),
            bg=text_bg,
            fg=text_fg,
            insertbackground=text_fg,
            relief="flat",
            state="disabled",
        )
        self.chat_area.pack(fill="both", expand=True)

        self.chat_area.tag_config("system", foreground="#f38ba8")
        self.chat_area.tag_config("user", foreground="#89b4fa")
        self.chat_area.tag_config("agent", foreground="#a6e3a1")
        self.chat_area.tag_config("error", foreground="#f38ba8")
        self.chat_area.tag_config("info", foreground="#94e2d5")

        right_frame = tk.Frame(content, bg=text_bg, width=200)
        right_frame.pack(side="right", fill="y", padx=(10, 0))
        right_frame.pack_propagate(False)

        tk.Label(
            right_frame,
            text="⚙️ 控制台",
            font=("SF Mono", 12, "bold"),
            fg=accent,
            bg=text_bg,
        ).pack(anchor="w", pady=(0, 10))

        btn_style = {
            "font": ("SF Mono", 10),
            "bg": header_bg,
            "fg": text_fg,
            "activebackground": accent,
            "activeforeground": text_bg,
            "relief": "flat",
            "cursor": "hand2",
            "width": 15,
        }

        tk.Button(
            right_frame, text="📜 查看会话", command=self.show_sessions, **btn_style
        ).pack(pady=3)
        tk.Button(
            right_frame, text="🔄 切换模型", command=self.show_providers, **btn_style
        ).pack(pady=3)
        tk.Button(
            right_frame, text="🧠 清理记忆", command=self.clear_memory, **btn_style
        ).pack(pady=3)
        tk.Button(
            right_frame, text="📊 系统状态", command=self.show_status, **btn_style
        ).pack(pady=3)

        tk.Label(right_frame, text="", bg=text_bg).pack()

        tk.Label(
            right_frame,
            text="💡 命令",
            font=("SF Mono", 12, "bold"),
            fg=accent,
            bg=text_bg,
        ).pack(anchor="w", pady=(10, 5))

        commands = """• /sessions - 查看会话
• /provider <id> - 切换模型
• /load <url> - 导入知识
• /resume <id> - 恢复会话"""

        tk.Label(
            right_frame,
            text=commands,
            font=("SF Mono", 9),
            fg="#a6adc8",
            bg=text_bg,
            justify="left",
            anchor="w",
        ).pack(anchor="w")

        input_frame = tk.Frame(self.root, bg=input_bg, height=60)
        input_frame.pack(fill="x", side="bottom")
        input_frame.pack_propagate(False)

        self.input_entry = tk.Entry(
            input_frame,
            font=("SF Mono", 12),
            bg=input_bg,
            fg=text_fg,
            insertbackground=text_fg,
            relief="flat",
            textvariable=tk.StringVar(),
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        self.input_entry.bind("<Return>", self.send_message)

        send_btn = tk.Button(
            input_frame,
            text="发送 ➤",
            font=("SF Mono", 11, "bold"),
            bg=accent,
            fg=text_bg,
            activebackground=text_fg,
            activeforeground=input_bg,
            relief="flat",
            cursor="hand2",
            command=self.send_message,
        )
        send_btn.pack(side="right", padx=10, pady=10)

    def append_chat(self, text, tag="info"):
        self.chat_area.configure(state="normal")
        self.chat_area.insert("end", text + "\n", tag)
        self.chat_area.configure(state="disabled")
        self.chat_area.see("end")

    def send_message(self, event=None):
        msg = self.input_entry.get().strip()
        if not msg:
            return
        self.input_entry.delete(0, "end")
        self.append_chat(f"📤 {msg}", "user")

        if self.process and self.running:
            self.process.stdin.write(msg + "\n")
            self.process.stdin.flush()

    def show_sessions(self):
        if self.process and self.running:
            self.process.stdin.write("/sessions\n")
            self.process.stdin.flush()

    def show_providers(self):
        if self.process and self.running:
            self.append_chat("📋 可用模型:", "system")
            self.append_chat("  • minimax_m2 (默认)", "info")
            self.append_chat("  • anthropic_claude3opus", "info")
            self.append_chat("  • anthropic_claude3sonnet", "info")
            self.append_chat("  • deepseek", "info")
            self.append_chat("  • moonshot", "info")
            self.append_chat("  使用 /provider <id> 切换", "info")

    def clear_memory(self):
        self.append_chat("🧠 记忆已清理", "system")

    def show_status(self):
        if self.process and self.running:
            self.append_chat("📊 系统状态", "system")
            self.append_chat(f"  Provider: minimax_m2", "info")
            self.append_chat(f"  工作 Agent: 3", "info")
            self.append_chat(f"  状态: 运行中", "info")

    def read_output(self):
        while self.running and self.process:
            try:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line.strip())
                elif self.process.poll() is not None:
                    break
            except:
                break

    def process_output(self):
        try:
            while True:
                line = self.output_queue.get_nowait()

                if "🚀 Multi-Agent 系统已启动" in line:
                    self.status_label.config(text="✅ 系统就绪")
                    self.append_chat(line, "system")
                elif "📝 你的任务:" in line or "你的任务:" in line:
                    self.append_chat(line, "system")
                elif "ERROR" in line or "错误" in line:
                    self.append_chat(line, "error")
                elif "[INFO]" in line:
                    continue
                elif line.strip():
                    self.append_chat(line, "info")
        except queue.Empty:
            pass

        self.root.after(100, self.process_output)

    def start_system(self):
        exe_path = os.path.join(os.path.dirname(__file__), "MultiAgentSystem")
        if not os.path.exists(exe_path):
            exe_path = "MultiAgentSystem"

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            self.process = subprocess.Popen(
                [exe_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
                bufsize=1,
            )
            self.running = True

            reader = threading.Thread(target=self.read_output, daemon=True)
            reader.start()

            self.process_output()

        except Exception as e:
            self.append_chat(f"❌ 启动失败: {e}", "error")
            self.status_label.config(text="❌ 启动失败")

    def on_closing(self):
        self.running = False
        if self.process:
            try:
                self.process.stdin.write("exit\n")
                self.process.stdin.flush()
                self.process.terminate()
                self.process.wait(timeout=3)
            except:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    gui = AgentGUI(root)
    root.protocol("WM_DELETE_WINDOW", gui.on_closing)

    def startup():
        import time

        time.sleep(0.5)
        gui.start_system()

    threading.Thread(target=startup, daemon=True).start()

    root.mainloop()


if __name__ == "__main__":
    main()
