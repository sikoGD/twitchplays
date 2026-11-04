# Twitch Plays controller

A lightweight, local Python controller that maps exact Twitch chat messages to keyboard presses for an emulator or game running on the same machine.

It uses Twitch's TLS IRC endpoint and keeps credentials out of source control.

## Windows release

Download the latest `TwitchPlays-windows-x64.zip` from the repository's **Releases** page and extract it. Keep `TwitchPlays.exe` and `TwitchPlaysController.exe` together in the same folder, then launch `TwitchPlays.exe`. Python does not need to be installed.

In the app, create a setup for a game or emulator, optionally choose a ROM, and launch it. Enter your Twitch bot credentials and start the controller. The token is used for that session and is not saved. Use the **Chat keyboard controls** section to customize chat-to-key bindings and key hold duration.

## Requirements

- Python 3.10 or later (source version only)
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

3. Start the desktop controller:

   ```powershell
   python ui.py
   ```

   Create a setup by choosing a name and browsing to a game executable or emulator. For an emulator, you can also select a ROM. Save the setup, then use **Launch selected game**. Some emulators need command line options; enter them in **Launch arguments** and use `{game}` where the ROM path should go. If `{game}` is omitted, the ROM path is appended.

   Enter the Twitch token, bot username, and channel, then select **Start Twitch controller**. The token is kept in memory for that session. Saved game setups are stored locally in `~/.twitchplays/profiles.json` and do not include Twitch credentials. To run the controller without the desktop window, set the environment variables above and run `python play.py`.

   The **Chat keyboard controls** section lets you customize the keyboard key for each exact command and adjust how long each key is held. These settings are saved per game setup. If Twitch disconnects, the controller retries the connection every five seconds.

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
