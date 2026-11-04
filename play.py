"""A small, local Twitch Plays controller.

Run with TWITCH_TOKEN, TWITCH_BOT_USERNAME, and TWITCH_CHANNEL set in the
environment. Commands are exact, case-insensitive chat messages such as `up`
or `start`; normal sentences do not trigger keyboard input.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import socket
import ssl
import sys
import threading
import time
from dataclasses import dataclass
from typing import Iterable

try:
    import pyautogui
except Exception:  # Makes tests usable in headless environments without GUI support.
    pyautogui = None


HOST = "irc.chat.twitch.tv"
PORT = 6697
COMMANDS = {
    "up": "w", "down": "s", "left": "a", "right": "d",
    "a": "z", "b": "x", "start": "enter", "l": "e", "r": "q",
}


@dataclass(frozen=True)
class Config:
    token: str
    bot_username: str
    channel: str
    key_hold_seconds: float = 0.08
    commands: dict[str, str] | None = None

    @classmethod
    def from_environment(cls) -> "Config":
        required = {
            "TWITCH_TOKEN": os.getenv("TWITCH_TOKEN", ""),
            "TWITCH_BOT_USERNAME": os.getenv("TWITCH_BOT_USERNAME", ""),
            "TWITCH_CHANNEL": os.getenv("TWITCH_CHANNEL", ""),
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError("Missing required environment variable(s): " + ", ".join(missing))
        hold_seconds = float(os.getenv("KEY_HOLD_SECONDS", "0.08"))
        if hold_seconds <= 0:
            raise ValueError("KEY_HOLD_SECONDS must be greater than zero")
        commands = COMMANDS.copy()
        raw_commands = os.getenv("TWITCH_COMMANDS", "")
        if raw_commands:
            try:
                overrides = json.loads(raw_commands)
            except json.JSONDecodeError as error:
                raise ValueError("TWITCH_COMMANDS must be a JSON object") from error
            if not isinstance(overrides, dict):
                raise ValueError("TWITCH_COMMANDS must be a JSON object")
            for command, key in overrides.items():
                if command not in COMMANDS:
                    raise ValueError(f"Unknown Twitch command: {command}")
                if not isinstance(key, str) or not key.strip():
                    raise ValueError(f"Keyboard key for '{command}' must be a non-empty string")
                normalized_key = key.strip().casefold()
                if pyautogui is not None and normalized_key not in pyautogui.KEYBOARD_KEYS:
                    raise ValueError(f"Unsupported keyboard key for '{command}': {key}")
                commands[command] = normalized_key
        return cls(
            token=required["TWITCH_TOKEN"].strip(),
            bot_username=required["TWITCH_BOT_USERNAME"].strip().lower(),
            channel=required["TWITCH_CHANNEL"].strip().lstrip("#").lower(),
            key_hold_seconds=hold_seconds,
            commands=commands,
        )

    @property
    def oauth_token(self) -> str:
        return self.token if self.token.startswith("oauth:") else f"oauth:{self.token}"


def parse_privmsg(line: str) -> tuple[str, str] | None:
    """Return (sender, message) for a Twitch IRC PRIVMSG, otherwise None."""
    if " PRIVMSG " not in line or " :" not in line:
        return None
    prefix, message = line.split(" :", 1)
    if not prefix.startswith(":") or "!" not in prefix:
        return None
    return prefix[1:].split("!", 1)[0], message.strip()


def command_from_message(message: str, commands: dict[str, str] | None = None) -> str | None:
    """Map an exact chat command to a configured keyboard key."""
    return (commands or COMMANDS).get(message.strip().casefold())


class GameController(threading.Thread):
    def __init__(self, actions: queue.Queue[str | None], hold_seconds: float) -> None:
        super().__init__(name="game-controller", daemon=True)
        self.actions = actions
        self.hold_seconds = hold_seconds

    def run(self) -> None:
        if pyautogui is None:
            logging.error("PyAutoGUI is unavailable. Install dependencies before running the controller.")
            return
        while True:
            key = self.actions.get()
            try:
                if key is None:
                    return
                pyautogui.keyDown(key)
                time.sleep(self.hold_seconds)
                pyautogui.keyUp(key)
                logging.info("Pressed %s", key)
            finally:
                self.actions.task_done()


class TwitchIrcClient:
    def __init__(self, config: Config, actions: queue.Queue[str | None]) -> None:
        self.config = config
        self.actions = actions
        self.socket: socket.socket | None = None

    def connect(self) -> None:
        raw_socket = socket.create_connection((HOST, PORT), timeout=15)
        self.socket = ssl.create_default_context().wrap_socket(raw_socket, server_hostname=HOST)
        self._send(f"PASS {self.config.oauth_token}")
        self._send(f"NICK {self.config.bot_username}")
        self._send("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands")
        self._send(f"JOIN #{self.config.channel}")

    def _send(self, message: str) -> None:
        if self.socket is None:
            raise RuntimeError("Not connected")
        self.socket.sendall(f"{message}\r\n".encode("utf-8"))

    def serve_forever(self) -> None:
        if self.socket is None:
            raise RuntimeError("Call connect before serve_forever")
        buffer = ""
        while True:
            received = self.socket.recv(4096)
            if not received:
                raise ConnectionError("Twitch closed the IRC connection")
            buffer += received.decode("utf-8", errors="replace")
            buffer, *lines = buffer.split("\r\n")
            for line in lines:
                self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        if line.startswith("PING"):
            self._send("PONG :tmi.twitch.tv")
            return
        parsed = parse_privmsg(line)
        if parsed is None:
            logging.debug("IRC: %s", line)
            return
        sender, message = parsed
        key = command_from_message(message, self.config.commands)
        if key:
            self.actions.put(key)
            logging.info("Queued %s from %s", message, sender)

    def close(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None


def main(argv: Iterable[str] | None = None) -> int:
    del argv
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = Config.from_environment()
    except ValueError as error:
        logging.error("%s", error)
        return 2
    if pyautogui is None:
        logging.error("PyAutoGUI is not installed. Run: python -m pip install -r requirements.txt")
        return 2

    actions: queue.Queue[str | None] = queue.Queue()
    controller = GameController(actions, config.key_hold_seconds)
    controller.start()
    try:
        while True:
            client = TwitchIrcClient(config, actions)
            try:
                client.connect()
                logging.info("Connected to #%s as %s", config.channel, config.bot_username)
                client.serve_forever()
            except (ConnectionError, OSError, ssl.SSLError) as error:
                logging.error("Twitch connection failed: %s", error)
                logging.info("Reconnecting in 5 seconds")
                client.close()
                time.sleep(5)
    except KeyboardInterrupt:
        logging.info("Stopping")
        return 0
    finally:
        actions.put(None)
        controller.join(timeout=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
