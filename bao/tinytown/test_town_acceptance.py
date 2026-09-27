"""Seed-42 full-town regression gate; skips when optional systems are absent."""

import copy
import importlib
import unittest


SYSTEM_MODULES = (
    "nori.tinytown",
    "nori.shops",
    "kiwi.townfolk",
    "sora.tinytown",
    "bao.tinytown",
    "kiwi.tinytown",
    "mochi.tinytown",
)
SHOP_IDS = {
    "one-mug-tea", "bench-and-bell", "spoke-and-spanner",
    "matcha-mile", "fold-post", "daifuku-cart",
}


class TownAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.engine = importlib.import_module("taro.tinytown.engine")
            cls.modules = [importlib.import_module(name) for name in SYSTEM_MODULES]
        except ImportError as error:
            raise unittest.SkipTest(f"Full town unavailable: {error}") from error

    def run_full_town(self):
        # Construct fresh systems for each run; never use the logger's CSV default.
        systems = [
            module.System(csv_path=None) if module.System.name == "log"
            else module.System()
            for module in self.modules
        ]
        history = []
        zero_streaks = dict.fromkeys(SHOP_IDS, 0)

        def check_day(town):
            day = town.day
            shops = town.state["businesses"]["shops"]
            self.assertEqual(set(shops), SHOP_IDS, f"Day {day}: shop roster changed")
            for shop_id, shop in shops.items():
                balance = shop["balance_cents"]
                self.assertGreaterEqual(
                    balance, 0, f"Day {day}: {shop_id} has negative balance {balance} cents"
                )
                zero_streaks[shop_id] = zero_streaks[shop_id] + 1 if balance == 0 else 0
                self.assertLessEqual(
                    zero_streaks[shop_id], 3,
                    f"Day {day}: {shop_id} has been at $0 for {zero_streaks[shop_id]} consecutive days",
                )
            for person in town.state["residents"]["people"]:
                self.assertGreaterEqual(
                    person["wallet_cents"], 0,
                    f"Day {day}: resident {person['id']} ({person['name']}) has "
                    f"negative wallet {person['wallet_cents']} cents",
                )
            congestion = town.state["traffic"]["congestion"]
            self.assertTrue(
                0 <= congestion <= 1,
                f"Day {day}: traffic congestion {congestion} is outside [0, 1]",
            )
            history.append(copy.deepcopy(town.state))

        town = self.engine.run_town(systems, seed=42, days=90, on_day=check_day)
        self.assertEqual(len(history), 90, "Expected snapshots for all 90 days")
        shops = town.state["businesses"]["shops"]
        closed = [shop_id for shop_id, shop in shops.items() if not shop["open"]]
        self.assertGreaterEqual(
            len(shops) - len(closed), 5,
            f"Day 90: fewer than 5 of 6 shops open; closed shops: {closed}",
        )
        self.assertEqual(
            town.state["businesses"]["open_count"], len(shops) - len(closed),
            "Day 90: businesses.open_count disagrees with individual shop states",
        )
        average = town.state["residents"]["avg_wallet_cents"]
        self.assertLess(average, 60000, f"Day 90: average wallet {average} cents must be below $600")
        self.assertIsNone(town.state["log"]["csv_path"], "CSV output must remain disabled")
        return town, history

    def test_seed_42_targets_and_determinism(self):
        first, first_history = self.run_full_town()
        second, second_history = self.run_full_town()
        for day, (first_state, second_state) in enumerate(zip(first_history, second_history), 1):
            self.assertEqual(first_state, second_state, f"Day {day}: seeded runs have different state")
        for day in range(91):
            self.assertEqual(
                [event for event in first.events if event["day"] == day],
                [event for event in second.events if event["day"] == day],
                f"Day {day}: seeded runs have different events",
            )
        self.assertEqual(first.rng.getstate(), second.rng.getstate(), "Day 90: final RNG states differ")


if __name__ == "__main__":
    unittest.main()
