# Twitch Plays controller

A lightweight, local Python controller that maps exact Twitch chat messages to keyboard presses for an emulator or game running on the same machine.

It uses Twitch's TLS IRC endpoint and keeps credentials out of source control.

## Requirements

- Python 3.10 or later
- A Twitch user access token with `chat:read` and `chat:edit` scopes
- The game/emulator focused in the foreground while the controller runs

## Setup

1. Create and activate a virtual environment:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

2. Copy `.env.example` to a private location (or set its variables in your shell). Do not commit the copied file or token.

   ```powershell
   $env:TWITCH_TOKEN = "oauth:your-token"
   $env:TWITCH_BOT_USERNAME = "your_bot_login"
   $env:TWITCH_CHANNEL = "your_channel_login"
   ```

3. Start the controller and focus the emulator/game window:

   ```powershell
   python play.py
   ```

## Chat commands

| Chat message | Key pressed |
| --- | --- |
| `up`, `down`, `left`, `right` | W, S, A, D |
| `a`, `b` | Z, X |
| `start` | Enter |
| `l`, `r` | E, Q |

Messages must exactly match a command (case-insensitive), which prevents normal chat such as â€œgo up thereâ€ from sending an input. `KEY_HOLD_SECONDS` optionally changes the press duration; its default is `0.08` seconds.

## Development

Run the tests with:

```powershell
python -m unittest -v
```

Twitch recommends EventSub plus the API for full chat bots, but this repository keeps the original local IRC-controller model. See the [Twitch IRC documentation](https://dev.twitch.tv/docs/chat/irc/) for token and connection details.

## Safety notes

- Never publish a Twitch OAuth token.
- Game ROMs, emulator executables, save files, and local configuration are intentionally excluded from Git. Supply games and emulators yourself and comply with their licences and applicable law.
