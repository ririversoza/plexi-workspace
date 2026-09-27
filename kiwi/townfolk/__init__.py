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
INCOME_TAX_PERCENT = 10
DAILY_RENT_CENTS = 600
DAILY_UTILITIES_CENTS = 150
ARREARS_MOOD_PENALTY = 15
HEALTHY_WALLET_CENTS = 10000
STAFF_COUNTS = {shop: 2 if shop in ("bench-and-bell", "spoke-and-spanner") else 1
                for shop in SHOP_IDS}
VISIT_CHANCE = {"sun": 0.65, "cloud": 0.55, "rain": 0.35, "snow": 0.20, "storm": 0.0}
MOOD_WEATHER_PENALTY = {"sun": 0, "cloud": 5, "rain": 10, "snow": 15, "storm": 25}


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _cents(value):
    """Refuse negative, fractional, boolean, or missing money/stock inputs."""
    return value if type(value) is int and value >= 0 else 0


def _summarize(state):
    people = state["people"]
    state["count"] = len(people)
    state["employed"] = sum(person["job"] is not None for person in people)
    state["avg_wallet_cents"] = (sum(person["wallet_cents"] for person in people) // len(people)
                                 if people else 0)
    state["arrears_cents"] = sum(person["arrears_cents"] for person in people)
    state["in_arrears"] = sum(person["arrears_cents"] > 0 for person in people)


def _update_mood(state, bought_today, condition="sun"):
    """Derived state only: no RNG, remembered mood, or economic side effects."""
    penalty = MOOD_WEATHER_PENALTY.get(condition, 0) if isinstance(condition, str) else 0
    bands = {"happy": 0, "ok": 0, "unhappy": 0}
    total = 0
    for person in state["people"]:
        wallet_points = min(40, _cents(person["wallet_cents"]) // 1000)
        employment_points = 10 if person["job"] is not None else -10
        purchase_points = 10 if person["id"] in bought_today else 0
        arrears_penalty = ARREARS_MOOD_PENALTY if _cents(person.get("arrears_cents")) else 0
        mood = max(0, min(100, 40 + wallet_points + employment_points + purchase_points
                           - penalty - arrears_penalty))
        person["mood"] = mood
        total += mood
        bands["happy" if mood >= 70 else "ok" if mood >= 40 else "unhappy"] += 1
    state["avg_mood"] = total // len(state["people"]) if state["people"] else 0
    state["mood_bands"] = bands


class System:
    name = "residents"

    def __init__(self, purchase_observer=None):
        # Optional reporting hook receives only immutable receipt values.
        self.purchase_observer = purchase_observer

    def setup(self, town):
        names = [f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES]
        jobs = [shop for shop in SHOP_IDS for _ in range(STAFF_COUNTS[shop])] + ["out-of-town"] * 94 + [None] * 18
        town.rng.shuffle(names)
        town.rng.shuffle(jobs)
        people = [
            {"id": index + 1, "name": name, "street": town.rng.choice(STREETS),
             "job": jobs[index], "wallet_cents": town.rng.randint(2000, 10000),
             "rent_arrears_cents": 0, "utility_arrears_cents": 0,
             "arrears_cents": 0, "taxes_paid_cents": 0,
             "rent_paid_cents": 0, "utilities_paid_cents": 0,
             "benefit_received_cents": 0}
            for index, name in enumerate(names)
        ]
        state = {"people": people, "purchases": {}, "spent_cents": {},
                 "taxes_paid_cents": 0, "rent_paid_cents": 0, "bills_paid_cents": 0,
                 "benefits_received_cents": 0}
        _summarize(state)
        _update_mood(state, set())
        town.state[self.name] = state

    def tick(self, town):
        state = town.state[self.name]
        businesses = _mapping(town.state.get("businesses"))
        economy = _mapping(town.state.get("economy"))
        benefit = _cents(economy.get("benefit_per_head_cents"))
        wages = _mapping(businesses.get("wages_paid"))
        shops = _mapping(businesses.get("shops"))
        weather = _mapping(town.state.get("weather"))
        condition = weather.get("condition")
        chance = VISIT_CHANCE.get(condition, 0.65) if isinstance(condition, str) else 0.65
        weekday = town.day >= 1 and (town.day - 1) % 7 < 5
        purchases, spent = {}, {}
        bought_today = set()
        stock, prices = {}, {}
        for shop_id in SHOP_IDS:
            shop = _mapping(shops.get(shop_id))
            price = _cents(shop.get("price_cents"))
            if shop.get("open") is True and price > 0:
                stock[shop_id] = _cents(shop.get("available"))
                prices[shop_id] = price
        people = list(state["people"])
        # Settle wages and fixed obligations before the shopping RNG is touched.
        for person in people:
            wage = _cents(wages.get(person["id"]))
            if weekday and person["job"] == "out-of-town":
                wage += WEEKDAY_WAGE_CENTS
            tax = wage * INCOME_TAX_PERCENT // 100
            person["wallet_cents"] += wage - tax
            person["benefit_received_cents"] = benefit if person["job"] is None else 0
            person["wallet_cents"] += person["benefit_received_cents"]
            person["taxes_paid_cents"] = tax
            person["rent_paid_cents"] = 0
            person["utilities_paid_cents"] = 0

            # Older debt takes priority; partial arrears payments avoid idle cash.
            for owed_key, paid_key in (("rent_arrears_cents", "rent_paid_cents"),
                                       ("utility_arrears_cents", "utilities_paid_cents")):
                paid = min(person["wallet_cents"], person[owed_key])
                person["wallet_cents"] -= paid
                person[owed_key] -= paid
                person[paid_key] += paid

            for amount, owed_key, paid_key, kind in (
                    (DAILY_RENT_CENTS, "rent_arrears_cents", "rent_paid_cents", "missed_rent"),
                    (DAILY_UTILITIES_CENTS, "utility_arrears_cents", "utilities_paid_cents", "missed_bill")):
                if person["wallet_cents"] >= amount:
                    person["wallet_cents"] -= amount
                    person[paid_key] += amount
                else:
                    person[owed_key] += amount
                    town.emit(kind, resident_id=person["id"], amount_cents=amount)
            person["arrears_cents"] = person["rent_arrears_cents"] + person["utility_arrears_cents"]
        state["taxes_paid_cents"] = sum(person["taxes_paid_cents"] for person in people)
        state["rent_paid_cents"] = sum(person["rent_paid_cents"] for person in people)
        state["bills_paid_cents"] = sum(person["utilities_paid_cents"] for person in people)
        state["benefits_received_cents"] = sum(person["benefit_received_cents"] for person in people)
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
                bought_today.add(person["id"])
                stock[shop_id] -= 1
                purchases[shop_id] = purchases.get(shop_id, 0) + 1
                spent[shop_id] = spent.get(shop_id, 0) + price
                if self.purchase_observer is not None:
                    self.purchase_observer(person["id"], shop_id, price)
        state["purchases"] = purchases
        state["spent_cents"] = spent
        _summarize(state)
        _update_mood(state, bought_today, condition)
