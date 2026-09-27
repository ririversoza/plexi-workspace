"""Diary tests run without any sibling system or disk output."""

import copy
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from kiwi.townfolk import System
from kiwi.townfolk.diary import Diary, main, run_diary
from kiwi.townfolk.test_residents import Town, businesses


def fake_run(systems, seed, days):
    town = Town(seed)
    town.history = []
    for system in systems:
        system.setup(town)
    for day in range(1, days + 1):
        town.day = day
        for system in systems:
            system.tick(town)
        town.history.append(json.dumps(town.state, separators=(",", ":")).encode())
    return town


class Shops:
    name = "businesses"

    def setup(self, town):
        pass

    def tick(self, town):
        town.state["businesses"] = businesses(capacity=20, price=town.day * 10 + 100)
        town.state["businesses"]["wages_paid"] = {1: 123, 2: 456}
        town.state["weather"] = {"condition": ("sun", "rain", "storm")[town.day % 3]}


class DiaryTests(unittest.TestCase):
    def test_determinism_receipts_conservation_and_no_behavior_change(self):
        first, town = run_diary(systems=[Shops(), System()], runner=fake_run)
        second, repeated = run_diary(systems=[Shops(), System()], runner=fake_run)
        plain = fake_run([Shops(), System()], seed=42, days=90)
        self.assertEqual(first.rows, second.rows)
        self.assertEqual(town.history, plain.history)
        self.assertEqual(town.rng.getstate(), plain.rng.getstate())
        self.assertEqual(town.rng.getstate(), repeated.rng.getstate())
        for rid, person in first.people.items():
            wallet = person["wallet_cents"]
            self.assertEqual(len(first.rows[rid]), 90)
            for row in first.rows[rid]:
                expected_wages = {1: 123, 2: 456}.get(rid, 0)
                if person["job"] == "out-of-town" and (row["day"] - 1) % 7 < 5:
                    expected_wages += 2000
                self.assertEqual(row["wage_in"], expected_wages)
                spent = sum(price for _, price in row["purchases"])
                self.assertEqual(row["wallet"], wallet + expected_wages - spent
                                 - row["tax_paid"] - row["rent_paid"]
                                 - row["utilities_paid"] + row["benefit_in"])
                wallet = row["wallet"]
                for _, price in row["purchases"]:
                    self.assertEqual(price, row["day"] * 10 + 100)
        for day, state_bytes in enumerate(town.history):
            state = json.loads(state_bytes)
            counts, totals = {}, {}
            for rows in first.rows.values():
                for shop, price in rows[day]["purchases"]:
                    counts[shop] = counts.get(shop, 0) + 1
                    totals[shop] = totals.get(shop, 0) + price
            self.assertEqual(counts, state["residents"]["purchases"])
            self.assertEqual(totals, state["residents"]["spent_cents"])

    def test_name_id_random_lookup_and_errors(self):
        diary, town = run_diary(systems=[System()], runner=fake_run)
        person = diary.select("1")
        self.assertEqual(person, diary.select("  " + person["name"].swapcase() + "  "))
        rng = town.rng.getstate()
        state = copy.deepcopy(town.state)
        picks = [diary.select(seed=seed, random_pick=True)["id"] for seed in range(20)]
        self.assertGreater(len(set(picks)), 1)
        self.assertEqual(picks, [diary.select(seed=seed, random_pick=True)["id"] for seed in range(20)])
        self.assertEqual(town.rng.getstate(), rng)
        self.assertEqual(town.state, state)
        for selector in ("0", "999", "missing name", ""):
            with self.assertRaisesRegex(ValueError, "No resident"):
                diary.select(selector)
        diary.people[2]["name"] = person["name"]
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            diary.select(person["name"])

    def test_missing_systems_and_log_disabled(self):
        class Log:
            name = "log"
            csv_path = "must-not-write.csv"

            def setup(self, town):
                if self.csv_path is not None:
                    raise AssertionError("CSV output enabled")

            def tick(self, town):
                pass
        diary, _ = run_diary(systems=[System(), Log()], runner=fake_run)
        text = diary.render(diary.select("1"), 42)
        self.assertIn("n/a", text)
        self.assertIn("Total spent: $0.00", text)
        self.assertIn("Favourite shop: none", text)
        self.assertTrue(all(row["purchases"] == () for row in diary.rows[1]))
        missing, _ = run_diary(systems=[], runner=fake_run)
        with self.assertRaisesRegex(ValueError, "not built yet"):
            missing.select("1")

    def test_summary_ties_and_mood_when_available(self):
        diary = Diary()
        person = {"id": 1, "name": "Ada Bell"}
        diary.rows[1] = [
            {"day": day, "weather": "sun", "job": None, "wage_in": 100,
             "purchases": ((shop, 50),), "wallet": 1000, "mood": mood}
            for day, shop, mood in ((1, "z-shop", 60), (2, "a-shop", 60), (3, "b-shop", 20))]
        text = diary.render(person, 42)
        self.assertIn("Total earned: $3.00 | Total benefits: $0.00 | Total spent: $1.50", text)
        self.assertIn("Favourite shop: a-shop", text)
        self.assertIn("Happiest: day 1 (60) | Saddest: day 3 (20)", text)

    def test_cli_errors_and_success(self):
        for args in ([], ["1", "--random-pick"], ["1", "--seed", "bad"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(error.exception.code, 2)
        diary, town = run_diary(systems=[System()], runner=fake_run)
        with patch("kiwi.townfolk.diary.run_diary", return_value=(diary, town)):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--random-pick", "--seed", "42"]), 0)
            self.assertIn("Diary:", output.getvalue())
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["not a resident"]), 1)
        missing = ModuleNotFoundError("engine absent", name="taro.tinytown")
        with patch("kiwi.townfolk.diary.run_diary", side_effect=missing), redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(main(["1"]), 1)
        self.assertIn("not built yet", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
