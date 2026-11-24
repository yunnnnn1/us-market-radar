# -*- coding: utf-8 -*-
"""Scheduled Actions must fan one Discord secret out to every webhook destination.

The safe quote-refresh workflow stays notification-off and must not receive it.
This file never reads secret values or contacts Discord.
"""
import os
import re
import unittest
from datetime import datetime
from unittest.mock import patch

import discord_sentinel as ds

ROOT = os.path.dirname(os.path.abspath(__file__))
SCHEDULED = os.path.join(ROOT, ".github", "workflows", "market_radar.yml")
SAFE_ONCE = os.path.join(ROOT, ".github", "workflows", "quote_refresh_once.yml")
SAME_SECRET = "${{ secrets.DISCORD_WEBHOOK_URL }}"
DESTINATIONS = (
    "DISCORD_WEBHOOK_URL",
    "DISCORD_SENTINEL_WEBHOOK_URL",
    "DISCORD_CLAW_WEBHOOK_URL",
    "DISCORD_DEFENSIVE_FLIGHT_WEBHOOK_URL",
    "DISCORD_DEFENSIVE_WEBHOOK_URL",
    "DISCORD_JIN10_WEBHOOK_URL",
)
NOT_DESTINATIONS = {"DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID"}
ENV_GET = re.compile(r"""os\.environ\.get\(\s*['"](DISCORD_[A-Z0-9_]+)['"]""")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _scan_step(workflow_text):
    marker = "执行全市场"
    pages = "请求本仓库 Pages"
    start = workflow_text.index(marker)
    end = workflow_text.index(pages, start)
    return workflow_text[start:end]


class TestDiscordActionsWiring(unittest.TestCase):
    def test_scheduled_workflow_maps_every_destination_to_one_secret(self):
        scan = _scan_step(_read(SCHEDULED))
        for name in DESTINATIONS:
            self.assertIn(f"{name}: {SAME_SECRET}", scan, name)
        self.assertEqual(scan.count(SAME_SECRET), len(DESTINATIONS))
        self.assertIn('RADAR_SENTINEL_NO_CATCHUP: "1"', scan)
        self.assertNotIn("DISCORD_BOT_TOKEN", scan)
        self.assertIn("notification_channels:", _read(SCHEDULED))
        self.assertIn("- discord_only", _read(SCHEDULED))
        self.assertIn('if [ "$NOTIFY_MODE" = "discord_only" ]; then', scan)
        self.assertIn("export RADAR_NOTIFY_CHANNELS=discord_only", scan)
        launch = [
            line.strip() for line in scan.splitlines()
            if line.strip().startswith("python integrated_market_radar.py")
        ]
        self.assertEqual(launch, [
            "python integrated_market_radar.py --loop-daemon --duration-minutes $DURATION --interval-seconds $INTERVAL"
        ])

    def test_schedule_timing_is_unchanged(self):
        text = _read(SCHEDULED)
        for cron in (
            "0 0 * * 1-5",
            "0 4 * * 1-5",
            "0 8 * * 1-5",
            "0 12 * * 1-5",
            "0 16 * * 1-5",
            "30 20 * * 1-5",
        ):
            self.assertIn(f"cron: '{cron}'", text)
        self.assertIn("--loop-daemon --duration-minutes $DURATION --interval-seconds $INTERVAL", text)

    def test_pages_step_does_not_receive_the_discord_secret(self):
        text = _read(SCHEDULED)
        pages = text.split("请求本仓库 Pages", 1)[1]
        self.assertNotIn("secrets.DISCORD", pages)
        self.assertNotIn("DISCORD_", pages)

    def test_safe_quote_refresh_has_no_discord_secret_and_stays_no_alert(self):
        text = _read(SAFE_ONCE)
        self.assertIn('RADAR_DISABLE_EXTERNAL_ALERTS: "1"', text)
        self.assertIn("AI_WEB_AUTO_BRIEF_ENABLED: \"0\"", text)
        self.assertIn("--once --no-alerts --no-browser", text)
        self.assertNotIn("secrets.DISCORD", text)
        for name in DESTINATIONS:
            self.assertNotIn(name, text)
        self.assertNotIn("DISCORD_BOT_TOKEN", text)
        self.assertNotIn("RADAR_SENTINEL_NO_CATCHUP", text)
        self.assertNotIn("notification_channels", text)
        self.assertNotIn("RADAR_NOTIFY_CHANNELS", text)

    def test_code_webhook_destinations_are_exactly_the_mapped_names(self):
        found = set()
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = [name for name in dirnames if name not in {".git", "__pycache__", "us-market-radar"}]
            for filename in filenames:
                if not filename.endswith(".py") or filename.startswith("test_"):
                    continue
                found.update(ENV_GET.findall(_read(os.path.join(dirpath, filename))))
        destinations = found - NOT_DESTINATIONS
        self.assertEqual(destinations, set(DESTINATIONS))

    def test_no_catchup_blocks_backlog_but_keeps_the_open_window(self):
        outside = datetime(2026, 11, 25, 17, 0)
        inside = datetime(2026, 11, 25, 9, 25)
        with patch.object(ds, "_load_sentinel_state", return_value={}):
            with patch.dict(os.environ, {"RADAR_SENTINEL_NO_CATCHUP": "1"}, clear=False):
                self.assertEqual(ds.check_sentinel_schedule_window(outside)[0], False)
                should_push, slot_id, _name, _day = ds.check_sentinel_schedule_window(inside)
                self.assertTrue(should_push)
                self.assertEqual(slot_id, "pre_market")
            should_push, slot_id, name, _day = ds.check_sentinel_schedule_window(outside)
            self.assertTrue(should_push)
            self.assertIn("补发", name)
            self.assertTrue(slot_id)


if __name__ == "__main__":
    unittest.main()
