import os
import unittest
from unittest.mock import patch

from play import Config, command_from_message, parse_privmsg


class CommandTests(unittest.TestCase):
    def test_command_must_be_exact(self):
        self.assertEqual(command_from_message(" UP "), "w")
        self.assertEqual(command_from_message("start"), "enter")
        self.assertIsNone(command_from_message("go up now"))

    def test_privmsg_parser(self):
        line = ":viewer!viewer@viewer.tmi.twitch.tv PRIVMSG #channel :up"
        self.assertEqual(parse_privmsg(line), ("viewer", "up"))
        self.assertIsNone(parse_privmsg("PING :tmi.twitch.tv"))

    def test_config_adds_oauth_prefix_and_normalizes_names(self):
        environment = {
            "TWITCH_TOKEN": "token",
            "TWITCH_BOT_USERNAME": "MyBot",
            "TWITCH_CHANNEL": "#MyChannel",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = Config.from_environment()
        self.assertEqual(config.oauth_token, "oauth:token")
        self.assertEqual(config.bot_username, "mybot")
        self.assertEqual(config.channel, "mychannel")


if __name__ == "__main__":
    unittest.main()
