"""Named residents, weekday wages, and stock-limited daily purchases."""

SHOP_IDS = (
    "one-mug-tea", "bench-and-bell", "spoke-and-spanner",
    "matcha-mile", "fold-post", "daifuku-cart",
)
FIRST_NAMES = (
    "Ada", "Ben", "Cora", "Dev", "Emi", "Finn", "Gia", "Hugo",
    "Iris", "Jules", "Kai", "Lena", "Milo", "Nia", "Omar",
)
LAST_NAMES = ("Ash", "Bell", "Chen", "Diaz", "Elm", "Fox", "Green", "Hill")
STREETS = ("Clover Lane", "Maple Street", "Orchard Road", "Willow Way")
WEEKDAY_WAGE_CENTS = 2000
HEALTHY_WALLET_CENTS = 10000
STAFF_COUNTS = {shop: 2 if shop in ("bench-and-bell", "spoke-and-spanner") else 1
                for shop in SHOP_IDS}
VISIT_CHANCE = {"sun": 0.65, "cloud": 0.55, "rain": 0.35, "snow": 0.20, "storm": 0.0}


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _cents(value):
    """Refuse negative, fractional, boolean, or missing money/stock inputs."""
    return value if type(value) is int and value >= 0 else 0


def _summarize(state):
    people = state["people"]
    state["count"] = len(people)
    state["employed"] = sum(person["job"] is not None for person in people)
    state["avg_wallet_cents"] = sum(person["wallet_cents"] for person in people) // len(people)


class System:
    name = "residents"

    def setup(self, town):
        names = [f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES]
        jobs = [shop for shop in SHOP_IDS for _ in range(STAFF_COUNTS[shop])] + ["out-of-town"] * 94 + [None] * 18
        town.rng.shuffle(names)
        town.rng.shuffle(jobs)
        people = [
            {"id": index + 1, "name": name, "street": town.rng.choice(STREETS),
             "job": jobs[index], "wallet_cents": town.rng.randint(2000, 10000)}
            for index, name in enumerate(names)
        ]
        state = {"people": people, "purchases": {}, "spent_cents": {}}
        _summarize(state)
        town.state[self.name] = state

    def tick(self, town):
        state = town.state[self.name]
        businesses = _mapping(town.state.get("businesses"))
        wages = _mapping(businesses.get("wages_paid"))
        shops = _mapping(businesses.get("shops"))
        weather = _mapping(town.state.get("weather"))
        condition = weather.get("condition")
        chance = VISIT_CHANCE.get(condition, 0.65) if isinstance(condition, str) else 0.65
        weekday = town.day >= 1 and (town.day - 1) % 7 < 5
        purchases, spent = {}, {}
        stock, prices = {}, {}
        for shop_id in SHOP_IDS:
            shop = _mapping(shops.get(shop_id))
            price = _cents(shop.get("price_cents"))
            if shop.get("open") is True and price > 0:
                stock[shop_id] = _cents(shop.get("available"))
                prices[shop_id] = price
        people = list(state["people"])
        # Credit every wallet before anyone shops; never write business state.
        for person in people:
            person["wallet_cents"] += _cents(wages.get(person["id"]))
            if weekday and person["job"] == "out-of-town":
                person["wallet_cents"] += WEEKDAY_WAGE_CENTS
        town.rng.shuffle(people)
        for person in people:
            if town.rng.random() >= chance:
                continue
            limit = 2 if person["wallet_cents"] > HEALTHY_WALLET_CENTS else 1
            visited = set()
            for _ in range(limit):
                candidates = [shop_id for shop_id in SHOP_IDS
                              if stock.get(shop_id, 0) > 0 and shop_id not in visited
                              and prices[shop_id] <= person["wallet_cents"]]
                if not candidates:
                    break
                shop_id = town.rng.choice(candidates)
                visited.add(shop_id)
                price = prices[shop_id]
                person["wallet_cents"] -= price
                stock[shop_id] -= 1
                purchases[shop_id] = purchases.get(shop_id, 0) + 1
                spent[shop_id] = spent.get(shop_id, 0) + price
        state["purchases"] = purchases
        state["spent_cents"] = spent
        _summarize(state)
