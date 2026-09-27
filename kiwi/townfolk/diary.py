"""Read-only resident diaries; run with python3 -m kiwi.townfolk.diary."""

import argparse
from collections import Counter, defaultdict
import hashlib
import sys


def money(cents):
    return f"${cents // 100}.{cents % 100:02d}"


class Diary:
    """Keep receipts and snapshots outside town state and the event stream."""

    def __init__(self):
        self.people = {}
        self.rows = defaultdict(list)
        self.receipts = defaultdict(list)

    def purchase(self, resident_id, shop_id, price_cents):
        self.receipts[resident_id].append((shop_id, price_cents))

    def observe(self, system):
        diary = self
        system.purchase_observer = self.purchase

        class ObservedResidents:
            name = system.name

            def setup(self, town):
                system.setup(town)
                for person in town.state.get("residents", {}).get("people", []):
                    diary.people[person["id"]] = dict(person)

            def tick(self, town):
                before = {p["id"]: p["wallet_cents"]
                          for p in town.state.get("residents", {}).get("people", [])}
                diary.receipts.clear()
                system.tick(town)
                weather = town.state.get("weather") or {}
                condition = weather.get("condition", "n/a") if isinstance(weather, dict) else "n/a"
                for person in town.state.get("residents", {}).get("people", []):
                    rid = person["id"]
                    purchases = tuple(diary.receipts.get(rid, ()))
                    spent = sum(price for _, price in purchases)
                    diary.rows[rid].append({
                        "day": town.day, "weather": condition, "job": person["job"],
                        "wage_in": person["wallet_cents"] - before[rid] + spent,
                        "purchases": purchases, "wallet": person["wallet_cents"],
                        "mood": person.get("mood"),
                    })

        return ObservedResidents()

    def select(self, selector=None, *, seed=42, random_pick=False):
        people = sorted(self.people.values(), key=lambda p: p["id"])
        if not people:
            raise ValueError("Residents are not built yet; no diary available.")
        if random_pick:
            index = int.from_bytes(hashlib.sha256(str(seed).encode("ascii")).digest(), "big") % len(people)
            return people[index]
        text = str(selector).strip()
        if text.isdecimal():
            matches = [p for p in people if p["id"] == int(text)]
        else:
            matches = [p for p in people if p["name"].casefold() == text.casefold()]
        if not matches:
            raise ValueError(f"No resident matches {text!r}; use an ID or full name.")
        if len(matches) > 1:
            raise ValueError(f"Name {text!r} is ambiguous; use a resident ID.")
        return matches[0]

    def render(self, person, seed):
        rows = self.rows[person["id"]]
        lines = [f"Diary: {person['name']} (#{person['id']}) | seed {seed}",
                 "Day | Weather | Job | Wage in | Purchases (shop @ price) | Wallet after | Mood"]
        for row in rows:
            purchases = ", ".join(f"{shop} @ {money(price)}" for shop, price in row["purchases"]) or "-"
            mood = row["mood"] if row["mood"] is not None else "n/a"
            lines.append(f"{row['day']:3} | {row['weather']} | {row['job'] or 'unemployed'} | "
                         f"{money(row['wage_in'])} | {purchases} | {money(row['wallet'])} | {mood}")
        earned = sum(row["wage_in"] for row in rows)
        spent = sum(price for row in rows for _, price in row["purchases"])
        shops = Counter(shop for row in rows for shop, _ in row["purchases"])
        favourite = min(shops, key=lambda shop: (-shops[shop], shop)) if shops else "none"
        moods = [row for row in rows if row["mood"] is not None]
        happiest = min(moods, key=lambda row: (-row["mood"], row["day"])) if moods else None
        saddest = min(moods, key=lambda row: (row["mood"], row["day"])) if moods else None
        def mood_day(row):
            return f"day {row['day']} ({row['mood']})" if row else "n/a (mood unavailable)"
        lines += [f"Total earned: {money(earned)} | Total spent: {money(spent)}",
                  f"Favourite shop: {favourite}",
                  f"Happiest: {mood_day(happiest)} | Saddest: {mood_day(saddest)}"]
        return "\n".join(lines)


def run_diary(seed=42, *, systems=None, runner=None):
    """Run the engine once, with CSV disabled and no reporting RNG draws."""
    if runner is None:
        from taro.tinytown.engine import run_town
        runner = run_town
    if systems is None:
        from taro.tinytown.run import load_systems
        systems = load_systems()
    diary = Diary()
    installed = []
    for system in systems:
        if system.name == "log":
            system.csv_path = None
        installed.append(diary.observe(system) if system.name == "residents" else system)
    town = runner(installed, seed=seed, days=90)
    return diary, town


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resident", nargs="?", help="resident ID or quoted full name")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--random-pick", action="store_true", help="choose by a stable hash of the seed")
    args = parser.parse_args(argv)
    if (args.resident is None and not args.random_pick) or (args.resident is not None and args.random_pick):
        parser.error("provide either a resident ID/name or --random-pick")
    try:
        diary, _ = run_diary(args.seed)
        person = diary.select(args.resident, seed=args.seed, random_pick=args.random_pick)
    except ModuleNotFoundError as error:
        if error.name in ("taro", "taro.tinytown", "taro.tinytown.engine", "taro.tinytown.run"):
            print("Town engine is not built yet; no diary available.", file=sys.stderr)
            return 1
        raise
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(diary.render(person, args.seed))
    return 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
