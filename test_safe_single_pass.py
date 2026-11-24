# -*- coding: utf-8 -*-
"""Guards for one quote pass that must not notify or stay resident."""
import os
import unittest
from unittest.mock import patch

import integrated_market_radar as imr


class TestSafeSinglePass(unittest.TestCase):
    def test_no_alerts_flag_sets_the_env_gate(self):
        previous = os.environ.pop("RADAR_DISABLE_EXTERNAL_ALERTS", None)
        try:
            self.assertTrue(imr.engage_no_alert_mode(["integrated_market_radar.py", "--once", "--no-alerts"]))
            self.assertEqual(os.environ.get("RADAR_DISABLE_EXTERNAL_ALERTS"), "1")
            self.assertTrue(imr._external_alerts_disabled())
        finally:
            if previous is None:
                os.environ.pop("RADAR_DISABLE_EXTERNAL_ALERTS", None)
            else:
                os.environ["RADAR_DISABLE_EXTERNAL_ALERTS"] = previous

    def test_guarded_once_does_not_start_the_star_server(self):
        self.assertFalse(
            imr.should_start_star_server(["integrated_market_radar.py", "--once", "--no-alerts"])
        )
        previous = os.environ.get("RADAR_DISABLE_EXTERNAL_ALERTS")
        os.environ["RADAR_DISABLE_EXTERNAL_ALERTS"] = "1"
        try:
            self.assertFalse(imr.should_start_star_server(["integrated_market_radar.py", "--once"]))
        finally:
            if previous is None:
                os.environ.pop("RADAR_DISABLE_EXTERNAL_ALERTS", None)
            else:
                os.environ["RADAR_DISABLE_EXTERNAL_ALERTS"] = previous

    def test_plain_once_still_starts_the_star_server(self):
        previous = os.environ.pop("RADAR_DISABLE_EXTERNAL_ALERTS", None)
        try:
            self.assertTrue(imr.should_start_star_server(["integrated_market_radar.py", "--once"]))
        finally:
            if previous is not None:
                os.environ["RADAR_DISABLE_EXTERNAL_ALERTS"] = previous

    def test_only_finnhub_source_counts_as_realtime(self):
        self.assertFalse(imr.quotes_include_finnhub({"BTC-USD": {"last": 1, "source": "yahoo"}}))
        self.assertFalse(imr.quotes_include_finnhub({"ANT": {"last": 1, "source": "tradingview"}}))
        self.assertTrue(imr.quotes_include_finnhub({"QQQ": {"last": 100, "source": "finnhub"}}))
        self.assertFalse(imr.quotes_include_finnhub({"QQQ": {"last": 0, "source": "finnhub"}}))

    def test_disabled_senders_do_not_open_the_network(self):
        with patch.object(imr.sys, "argv", ["integrated_market_radar.py", "--once", "--no-alerts"]):
            with patch("urllib.request.urlopen") as urlopen, patch("requests.post") as post:
                self.assertFalse(imr.send_discord_claw_alert("t", "body", webhook_url="https://example.invalid/hook"))
                self.assertFalse(imr.send_pushplus_wechat_alert("t", "body"))
                urlopen.assert_not_called()
                post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
