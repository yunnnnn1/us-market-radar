# -*- coding: utf-8 -*-
"""Discord-only mode keeps the Discord mirror and blocks PushPlus HTTP.

No live webhook or PushPlus request is made. Tokens below are fixtures.
"""
import os
import unittest
from unittest.mock import patch

import integrated_market_radar as imr


class _FakeResponse:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b'{"code":200,"msg":"ok"}'


class TestDiscordOnlyNotify(unittest.TestCase):
    def setUp(self):
        self._token = imr.PUSHPLUS_TOKEN
        self._env = {
            "RADAR_NOTIFY_CHANNELS": os.environ.get("RADAR_NOTIFY_CHANNELS"),
            "RADAR_DISABLE_EXTERNAL_ALERTS": os.environ.get("RADAR_DISABLE_EXTERNAL_ALERTS"),
            "DISCORD_CLAW_WEBHOOK_URL": os.environ.get("DISCORD_CLAW_WEBHOOK_URL"),
        }

    def tearDown(self):
        imr.PUSHPLUS_TOKEN = self._token
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _send(self, mode, token="unit-test-pushplus-token"):
        os.environ.pop("RADAR_DISABLE_EXTERNAL_ALERTS", None)
        if mode:
            os.environ["RADAR_NOTIFY_CHANNELS"] = mode
        else:
            os.environ.pop("RADAR_NOTIFY_CHANNELS", None)
        os.environ["DISCORD_CLAW_WEBHOOK_URL"] = "https://example.invalid/unit-discord"
        imr.PUSHPLUS_TOKEN = token
        opened = []

        def fake_urlopen(req, timeout=12):
            url = getattr(req, "full_url", "")
            opened.append(url)
            if "pushplus.plus" in url:
                raise AssertionError("PushPlus HTTP was called")
            return _FakeResponse()

        with patch.object(imr.urllib.request, "urlopen", side_effect=fake_urlopen), \
                patch.object(imr.shared_alert_state, "is_sent", return_value=False), \
                patch.object(imr.shared_alert_state, "mark", return_value=True), \
                patch.object(imr.sys, "argv", ["integrated_market_radar.py"]):
            ok = imr.send_pushplus_wechat_alert("unit title", "unit body")
        return ok, opened

    def test_discord_only_mirrors_discord_and_blocks_pushplus_http(self):
        ok, opened = self._send("discord_only")
        self.assertTrue(ok)
        self.assertTrue(any("example.invalid/unit-discord" in url for url in opened))
        self.assertFalse(any("pushplus.plus" in url for url in opened))
        self.assertEqual(imr.notify_channel_mode(), "discord_only")
        self.assertFalse(imr.pushplus_http_allowed())

    def test_default_mode_still_calls_pushplus_when_token_exists(self):
        opened = []

        def record(req, timeout=12):
            opened.append(getattr(req, "full_url", ""))
            return _FakeResponse()

        os.environ.pop("RADAR_DISABLE_EXTERNAL_ALERTS", None)
        os.environ.pop("RADAR_NOTIFY_CHANNELS", None)
        os.environ["DISCORD_CLAW_WEBHOOK_URL"] = "https://example.invalid/unit-discord"
        imr.PUSHPLUS_TOKEN = "unit-test-pushplus-token"
        with patch.object(imr.urllib.request, "urlopen", side_effect=record), \
                patch.object(imr.shared_alert_state, "is_sent", return_value=False), \
                patch.object(imr.shared_alert_state, "mark", return_value=True), \
                patch.object(imr.sys, "argv", ["integrated_market_radar.py"]):
            ok = imr.send_pushplus_wechat_alert("unit title", "unit body")
        self.assertTrue(ok)
        self.assertTrue(any("example.invalid/unit-discord" in url for url in opened))
        self.assertTrue(any("pushplus.plus/send" in url for url in opened))
        self.assertTrue(imr.pushplus_http_allowed())

    def test_no_alerts_still_blocks_discord_and_pushplus(self):
        os.environ["RADAR_DISABLE_EXTERNAL_ALERTS"] = "1"
        os.environ["RADAR_NOTIFY_CHANNELS"] = "discord_only"
        imr.PUSHPLUS_TOKEN = "unit-test-pushplus-token"
        with patch.object(imr.urllib.request, "urlopen") as urlopen, \
                patch.object(imr.sys, "argv", ["integrated_market_radar.py", "--no-alerts"]):
            self.assertFalse(imr.send_pushplus_wechat_alert("unit title", "unit body"))
            urlopen.assert_not_called()
        self.assertFalse(imr.pushplus_http_allowed())

    def test_radar_pushplus_url_is_behind_the_guard(self):
        path = os.path.join(os.path.dirname(__file__), "integrated_market_radar.py")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(text.count("https://www.pushplus.plus/send"), 1)
        guard = text.index("if not pushplus_http_allowed()")
        url = text.index("https://www.pushplus.plus/send")
        self.assertLess(guard, url)
        self.assertIn("while (duration_min <= 0)", text)

    def test_empty_pushplus_token_still_returns_discord_success(self):
        ok, opened = self._send("", token="")
        self.assertTrue(ok)
        self.assertTrue(any("example.invalid/unit-discord" in url for url in opened))
        self.assertFalse(any("pushplus.plus" in url for url in opened))


if __name__ == "__main__":
    unittest.main()
