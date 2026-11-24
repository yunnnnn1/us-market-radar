# -*- coding: utf-8 -*-
"""This fork must never select the upstream repository as a push target."""
import os
import unittest

import integrated_market_radar as imr


class TestForkPublishTarget(unittest.TestCase):
    def test_actions_repository_is_used_when_it_is_this_fork(self):
        self.assertEqual(
            imr.publish_repo_slug({"GITHUB_REPOSITORY": "yunnnnn1/us-market-radar"}),
            "yunnnnn1/us-market-radar",
        )

    def test_upstream_repository_is_rejected(self):
        self.assertEqual(
            imr.publish_repo_slug({"GITHUB_REPOSITORY": "2827173579/us-market-radar"}),
            "yunnnnn1/us-market-radar",
        )

    def test_local_daemon_defaults_to_this_fork(self):
        self.assertEqual(imr.publish_repo_slug({}), "yunnnnn1/us-market-radar")

    def test_checked_in_sources_do_not_push_to_upstream(self):
        root = os.path.dirname(os.path.abspath(__file__))
        for name in ("integrated_market_radar.py", "android_tablet/TradeRadar_Android.py", ".github/workflows/market_radar.yml"):
            with open(os.path.join(root, name), encoding="utf-8") as handle:
                text = handle.read()
            self.assertNotIn("github.com/2827173579/us-market-radar.git", text, name)
            self.assertNotIn("2827173579.github.io", text, name)


if __name__ == "__main__":
    unittest.main()
