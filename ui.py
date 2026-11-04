"""Desktop launcher for a game or emulator and the Twitch Plays controller."""

from __future__ import annotations

import json
import os
import queue
import shlex
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ROOT = Path(__file__).resolve().parent
PROFILE_FILE = Path.home() / ".twitchplays" / "profiles.json"
BG = "#10141d"
PANEL = "#181f2b"
TEXT = "#edf2fa"
MUTED = "#9aa8ba"
ACCENT = "#a970ff"
DEFAULT_KEYS = {
    "up": "w", "down": "s", "left": "a", "right": "d",
    "a": "z", "b": "x", "start": "enter", "l": "e", "r": "q",
}


class ControllerUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Twitch Plays - Stream Setup")
        self.geometry("760x950")
        self.minsize(620, 800)
        self.configure(bg=BG)
        self.controller_process: subprocess.Popen[str] | None = None
        self.messages: queue.Queue[str] = queue.Queue()
        self.profiles = self._load_profiles()
        self.current_profile_name: str | None = None
        self._build()
        self._refresh_profile_list()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _load_profiles(self) -> dict[str, dict[str, object]]:
        try:
            data = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                profiles: dict[str, dict[str, object]] = {}
                for name, profile in data.items():
                    if not isinstance(profile, dict):
                        continue
                    saved = {
                        key: str(profile.get(key, ""))
                        for key in ("application", "game_file", "arguments", "key_hold_seconds")
                    }
                    keymap = profile.get("keymap")
                    saved["keymap"] = {
                        command: str(key)
                        for command, key in keymap.items()
                        if command in DEFAULT_KEYS and isinstance(key, str)
                    } if isinstance(keymap, dict) else DEFAULT_KEYS.copy()
                    profiles[str(name)] = saved
                return profiles
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save_profiles(self) -> None:
        PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROFILE_FILE.write_text(
            json.dumps(self.profiles, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

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
                        insertcolor=TEXT, bordercolor="#303b4b", padding=8)
        style.configure("TCombobox", fieldbackground="#0e131b", foreground=TEXT,
                        background="#303b4b", padding=7)
        style.configure("Go.TButton", background=ACCENT, foreground="white",
                        font=("Segoe UI", 10, "bold"), padding=(14, 9), borderwidth=0)
        style.map("Go.TButton", background=[("disabled", "#54456b"), ("active", "#bb91ff")])
        style.configure("Alt.TButton", background="#303b4b", foreground=TEXT,
                        font=("Segoe UI", 9, "bold"), padding=(11, 8), borderwidth=0)

        outer = ttk.Frame(self, padding=(24, 20))
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Twitch Plays", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Choose a game or emulator, then connect your Twitch chat.",
                  style="Hint.TLabel").pack(anchor="w", pady=(3, 14))

        game_card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        game_card.pack(fill="x")
        self._section_title(game_card, "GAME SETUP")
        profile_row = ttk.Frame(game_card, style="Card.TFrame")
        profile_row.pack(fill="x", pady=(0, 12))
        ttk.Label(profile_row, text="Saved setup", style="Card.TLabel").pack(side="left")
        self.profile_choice = ttk.Combobox(profile_row, state="readonly", width=25)
        self.profile_choice.pack(side="left", padx=(10, 8))
        self.profile_choice.bind("<<ComboboxSelected>>", self._select_profile)
        ttk.Button(profile_row, text="New", style="Alt.TButton",
                   command=self._new_profile).pack(side="left")
        ttk.Button(profile_row, text="Remove", style="Alt.TButton",
                   command=self._remove_profile).pack(side="right")

        self.profile_name = self._field(game_card, "SETUP NAME", "e.g. Emerald on VBA-M")
        self.application = self._path_field(game_card, "GAME OR EMULATOR APPLICATION", "Browse...",
                                             self._browse_application)
        self.game_file = self._path_field(game_card, "GAME FILE / ROM (OPTIONAL)", "Browse...",
                                           self._browse_game_file)
        self.arguments = self._field(game_card, "LAUNCH ARGUMENTS (OPTIONAL)", "")
        ttk.Label(game_card,
                  text='For emulator arguments, use {game} where the ROM path belongs. If omitted, the ROM path is added at the end.',
                  style="Hint.TLabel", wraplength=680).pack(anchor="w", pady=(0, 10))
        game_actions = ttk.Frame(game_card, style="Card.TFrame")
        game_actions.pack(fill="x")
        ttk.Button(game_actions, text="Save setup", style="Alt.TButton",
                   command=self._save_profile).pack(side="left")
        ttk.Button(game_actions, text="Launch selected game", style="Go.TButton",
                   command=self._launch_game).pack(side="right")

        mapping_card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        mapping_card.pack(fill="x", pady=(12, 0))
        self._section_title(mapping_card, "CHAT KEYBOARD CONTROLS")
        key_grid = ttk.Frame(mapping_card, style="Card.TFrame")
        key_grid.pack(fill="x")
        for column in range(3):
            key_grid.columnconfigure(column, weight=1)
        self.key_entries: dict[str, ttk.Entry] = {}
        for index, (command, default_key) in enumerate(DEFAULT_KEYS.items()):
            column, row = index % 3, index // 3
            cell = ttk.Frame(key_grid, style="Card.TFrame")
            cell.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0), pady=3)
            ttk.Label(cell, text=f"{command.upper()} key", style="Card.TLabel",
                      foreground=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
            entry = ttk.Entry(cell)
            entry.pack(fill="x", pady=(3, 2))
            entry.insert(0, default_key)
            self.key_entries[command] = entry
        self.hold_seconds = self._field(mapping_card, "KEY HOLD (SECONDS)", "0.08")
        ttk.Label(mapping_card, text="Set the key sent for each exact chat command. These settings are saved with each game setup.",
                  style="Hint.TLabel", wraplength=680).pack(anchor="w")

        twitch_card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        twitch_card.pack(fill="x", pady=(12, 0))
        self._section_title(twitch_card, "TWITCH CONNECTION")
        self.token = self._field(twitch_card, "ACCESS TOKEN", secret=True)
        credentials = ttk.Frame(twitch_card, style="Card.TFrame")
        credentials.pack(fill="x")
        credentials.columnconfigure(0, weight=1)
        credentials.columnconfigure(1, weight=1)
        self.username = self._field(credentials, "BOT USERNAME", "your_bot_login", column=0)
        self.channel = self._field(credentials, "CHANNEL", "your_channel_login", column=1)

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(10, 8))
        self.status = ttk.Label(controls, text="Offline", foreground=MUTED)
        self.status.pack(side="left", pady=8)
        self.start_button = ttk.Button(controls, text="Start Twitch controller",
                                       style="Go.TButton", command=self._start_controller)
        self.start_button.pack(side="right")
        self.stop_button = ttk.Button(controls, text="Stop", style="Alt.TButton",
                                      command=self._stop_controller, state="disabled")
        self.stop_button.pack(side="right", padx=(0, 8))

        ttk.Label(outer, text="ACTIVITY", style="Hint.TLabel").pack(anchor="w", pady=(2, 6))
        self.log = tk.Text(outer, bg="#0b1017", fg="#c8d5e5", insertbackground=TEXT,
                           font=("Consolas", 9), relief="flat", padx=12, pady=10,
                           wrap="word", state="disabled", height=5)
        self.log.pack(fill="both", expand=True)
        self._write("Select or create a setup. The game and Twitch controller can be started separately.")

    def _section_title(self, parent: ttk.Frame, title: str) -> None:
        ttk.Label(parent, text=title, style="Card.TLabel", foreground=MUTED,
                  font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 10))

    def _field(self, parent: ttk.Frame, label: str, placeholder: str = "",
               secret: bool = False, column: int | None = None) -> ttk.Entry:
        frame = ttk.Frame(parent, style="Card.TFrame") if column is not None else parent
        if column is not None:
            frame.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
        ttk.Label(frame, text=label, style="Card.TLabel", foreground=MUTED,
                  font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))
        entry = ttk.Entry(frame, show="*" if secret else "")
        entry.pack(fill="x", pady=(0, 9))
        if placeholder and not secret:
            entry.insert(0, placeholder)
        return entry

    def _path_field(self, parent: ttk.Frame, label: str, button: str,
                    browse_command: object) -> ttk.Entry:
        ttk.Label(parent, text=label, style="Card.TLabel", foreground=MUTED,
                  font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=(0, 9))
        entry = ttk.Entry(row)
        entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text=button, style="Alt.TButton", command=browse_command).pack(side="left", padx=(8, 0))
        return entry

    @staticmethod
    def _set_entry(entry: ttk.Entry, value: str) -> None:
        entry.delete(0, "end")
        entry.insert(0, value)

    def _browse_application(self) -> None:
        path = filedialog.askopenfilename(title="Choose a game or emulator application")
        if path:
            self._set_entry(self.application, path)

    def _browse_game_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a game file or ROM",
            filetypes=[("Game files", "*.gba *.gbc *.gb *.nes *.rom *.iso *.cue *.zip"),
                       ("All files", "*.*")],
        )
        if path:
            self._set_entry(self.game_file, path)

    def _refresh_profile_list(self, select: str | None = None) -> None:
        names = sorted(self.profiles, key=str.casefold)
        self.profile_choice.configure(values=names)
        if select and select in self.profiles:
            self.profile_choice.set(select)
            self._show_profile(select)
        elif names:
            selected = self.current_profile_name if self.current_profile_name in names else names[0]
            self.profile_choice.set(selected)
            self._show_profile(selected)
        else:
            self.profile_choice.set("")

    def _select_profile(self, _event: object = None) -> None:
        name = self.profile_choice.get()
        if name in self.profiles:
            self._show_profile(name)

    def _show_profile(self, name: str) -> None:
        profile = self.profiles[name]
        self.current_profile_name = name
        self._set_entry(self.profile_name, name)
        self._set_entry(self.application, profile.get("application", ""))
        self._set_entry(self.game_file, profile.get("game_file", ""))
        self._set_entry(self.arguments, profile.get("arguments", ""))
        keymap = profile.get("keymap", DEFAULT_KEYS)
        if not isinstance(keymap, dict):
            keymap = DEFAULT_KEYS
        for command, default_key in DEFAULT_KEYS.items():
            self._set_entry(self.key_entries[command], str(keymap.get(command, default_key)))
        self._set_entry(self.hold_seconds, str(profile.get("key_hold_seconds", "0.08")))

    def _new_profile(self) -> None:
        base, number = "New setup", 2
        name = base
        while name in self.profiles:
            name = f"{base} {number}"
            number += 1
        self.current_profile_name = None
        self.profile_choice.set("")
        self._set_entry(self.profile_name, name)
        self._set_entry(self.application, "")
        self._set_entry(self.game_file, "")
        self._set_entry(self.arguments, "")
        for command, key in DEFAULT_KEYS.items():
            self._set_entry(self.key_entries[command], key)
        self._set_entry(self.hold_seconds, "0.08")

    def _save_profile(self) -> None:
        name = self.profile_name.get().strip()
        application = self.application.get().strip()
        if not name or not application:
            messagebox.showerror("Missing setup details", "Enter a setup name and choose a game or emulator application.")
            return
        try:
            hold_seconds = float(self.hold_seconds.get().strip())
            if hold_seconds <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid key hold", "Key hold duration must be a number greater than zero.")
            return
        keymap = {command: entry.get().strip().casefold()
                  for command, entry in self.key_entries.items()}
        if not all(keymap.values()):
            messagebox.showerror("Missing key binding", "Enter a keyboard key for every chat command.")
            return
        if name != self.current_profile_name and name in self.profiles:
            messagebox.showerror("Name already used", "Choose a different setup name.")
            return
        if self.current_profile_name and self.current_profile_name != name:
            self.profiles.pop(self.current_profile_name, None)
        self.profiles[name] = {
            "application": application,
            "game_file": self.game_file.get().strip(),
            "arguments": self.arguments.get().strip(),
            "keymap": keymap,
            "key_hold_seconds": str(hold_seconds),
        }
        self.current_profile_name = name
        try:
            self._save_profiles()
        except OSError as error:
            messagebox.showerror("Could not save setup", str(error))
            return
        self._refresh_profile_list(select=name)
        self._write(f"Saved setup: {name}")

    def _remove_profile(self) -> None:
        name = self.profile_choice.get()
        if name not in self.profiles:
            return
        if not messagebox.askyesno("Remove setup", f"Remove the saved setup '{name}'?"):
            return
        self.profiles.pop(name)
        try:
            self._save_profiles()
        except OSError as error:
            messagebox.showerror("Could not save changes", str(error))
            return
        self.current_profile_name = None
        self._refresh_profile_list()
        self._write(f"Removed setup: {name}")

    def _launch_game(self) -> None:
        application = self.application.get().strip()
        game_file = self.game_file.get().strip()
        if not application or not Path(application).is_file():
            messagebox.showerror("Application not found", "Choose an existing game or emulator application.")
            return
        if game_file and not Path(game_file).is_file():
            messagebox.showerror("Game file not found", "Choose an existing game file or clear the optional field.")
            return
        try:
            command = [application]
            arguments = shlex.split(self.arguments.get().strip())
            has_game_placeholder = any("{game}" in argument for argument in arguments)
            command.extend(argument.replace("{game}", game_file) for argument in arguments)
            if game_file and not has_game_placeholder:
                command.append(game_file)
            subprocess.Popen(command, cwd=str(Path(application).parent))
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not launch", str(error))
            return
        self._write(f"Launched {Path(application).name}")

    def _start_controller(self) -> None:
        values = (self.token.get().strip(), self.username.get().strip(), self.channel.get().strip())
        if not all(values):
            messagebox.showerror("Twitch details needed", "Enter the access token, bot username, and channel.")
            return
        if self.controller_process and self.controller_process.poll() is None:
            return
        try:
            hold_seconds = float(self.hold_seconds.get().strip())
            if hold_seconds <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid key hold", "Key hold duration must be a number greater than zero.")
            return
        keymap = {command: entry.get().strip().casefold()
                  for command, entry in self.key_entries.items()}
        if not all(keymap.values()):
            messagebox.showerror("Missing key binding", "Enter a keyboard key for every chat command.")
            return
        env = os.environ.copy()
        env.update(TWITCH_TOKEN=values[0], TWITCH_BOT_USERNAME=values[1],
                   TWITCH_CHANNEL=values[2].lstrip("#"),
                   KEY_HOLD_SECONDS=str(hold_seconds),
                   TWITCH_COMMANDS=json.dumps(keymap))
        self.controller_process = subprocess.Popen(
            [sys.executable, str(ROOT / "play.py")], cwd=ROOT, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        process = self.controller_process
        threading.Thread(target=self._read_output, args=(process,), daemon=True).start()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.configure(text="Connecting...", foreground="#ffd166")

    def _read_output(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout
        for line in process.stdout:
            self.messages.put(line.rstrip())

    def _poll(self) -> None:
        while not self.messages.empty():
            line = self.messages.get_nowait()
            self._write(line)
            if "Connected to #" in line:
                self.status.configure(text="Connected", foreground="#65d69a")
        if self.controller_process and self.controller_process.poll() is not None:
            self.controller_process = None
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status.configure(text="Offline", foreground=MUTED)
        self.after(100, self._poll)

    def _write(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _stop_controller(self) -> None:
        if self.controller_process and self.controller_process.poll() is None:
            self.controller_process.terminate()
            self._write("Stopping Twitch controller...")

    def _close(self) -> None:
        self._stop_controller()
        self.destroy()


if __name__ == "__main__":
    ControllerUI().mainloop()
