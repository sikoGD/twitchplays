"""Small desktop launcher for the Twitch Plays controller."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk


ROOT = Path(__file__).resolve().parent
BG = "#10141d"
PANEL = "#181f2b"
TEXT = "#edf2fa"
MUTED = "#9aa8ba"
ACCENT = "#a970ff"


class ControllerUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Twitch Plays · Controller")
        self.geometry("680x640")
        self.minsize(560, 560)
        self.configure(bg=BG)
        self.process: subprocess.Popen[str] | None = None
        self.messages: queue.Queue[str] = queue.Queue()
        self._build()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        style.configure("Hint.TLabel", foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Card.TLabel", background=PANEL)
        style.configure("TEntry", fieldbackground="#0e131b", foreground=TEXT,
                        insertcolor=TEXT, bordercolor="#303b4b", padding=9)
        style.configure("Go.TButton", background=ACCENT, foreground="white",
                        font=("Segoe UI", 10, "bold"), padding=(16, 10), borderwidth=0)
        style.map("Go.TButton", background=[("disabled", "#54456b"), ("active", "#bb91ff")])
        style.configure("Stop.TButton", background="#303b4b", foreground=TEXT,
                        font=("Segoe UI", 10, "bold"), padding=(16, 10), borderwidth=0)

        outer = ttk.Frame(self, padding=(28, 24))
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Twitch Plays", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Connect chat commands to your game controls.",
                  style="Hint.TLabel").pack(anchor="w", pady=(3, 18))

        card = ttk.Frame(outer, style="Card.TFrame", padding=18)
        card.pack(fill="x")
        self.token = self._field(card, "ACCESS TOKEN", "oauth:…", True)
        self.username = self._field(card, "BOT USERNAME", "your_bot_login")
        self.channel = self._field(card, "CHANNEL", "your_channel_login")

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(15, 14))
        self.status = ttk.Label(controls, text="●  Offline", foreground=MUTED)
        self.status.pack(side="left", pady=9)
        self.start_button = ttk.Button(controls, text="Start controller", style="Go.TButton",
                                       command=self._start)
        self.start_button.pack(side="right")
        self.stop_button = ttk.Button(controls, text="Stop", style="Stop.TButton",
                                      command=self._stop, state="disabled")
        self.stop_button.pack(side="right", padx=(0, 8))

        ttk.Label(outer, text="ACTIVITY", style="Hint.TLabel").pack(anchor="w", pady=(4, 7))
        self.log = tk.Text(outer, bg="#0b1017", fg="#c8d5e5", insertbackground=TEXT,
                           font=("Consolas", 9), relief="flat", padx=13, pady=12,
                           wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)
        self._write("Ready. Focus your game window after connecting.")
        ttk.Label(outer, text="Commands: ↑ ↓ ← →  ·  A / B  ·  Start  ·  L / R",
                  style="Hint.TLabel").pack(anchor="w", pady=(10, 0))

    def _field(self, parent: ttk.Frame, label: str, placeholder: str,
               secret: bool = False) -> ttk.Entry:
        ttk.Label(parent, text=label, style="Card.TLabel", foreground=MUTED,
                  font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 5))
        entry = ttk.Entry(parent, show="●" if secret else "")
        entry.pack(fill="x", pady=(0, 13))
        if not secret:
            entry.insert(0, placeholder)
        return entry

    def _start(self) -> None:
        values = (self.token.get().strip(), self.username.get().strip(), self.channel.get().strip())
        if not all(values):
            self._write("Enter the token, bot username, and channel to connect.")
            return
        env = os.environ.copy()
        env.update(TWITCH_TOKEN=values[0], TWITCH_BOT_USERNAME=values[1],
                   TWITCH_CHANNEL=values[2].lstrip("#"))
        self.process = subprocess.Popen([sys.executable, str(ROOT / "play.py")], cwd=ROOT,
                                        env=env, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, bufsize=1)
        threading.Thread(target=self._read_output, daemon=True).start()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.configure(text="●  Connecting…", foreground="#ffd166")

    def _read_output(self) -> None:
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            self.messages.put(line.rstrip())

    def _poll(self) -> None:
        while not self.messages.empty():
            line = self.messages.get_nowait()
            self._write(line)
            if "Connected to #" in line:
                self.status.configure(text="●  Connected", foreground="#65d69a")
        if self.process and self.process.poll() is not None:
            self.process = None
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status.configure(text="●  Offline", foreground=MUTED)
        self.after(100, self._poll)

    def _write(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self._write("Stopping controller…")

    def _close(self) -> None:
        self._stop()
        self.destroy()


if __name__ == "__main__":
    ControllerUI().mainloop()
