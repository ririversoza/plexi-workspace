import copy
import unittest

from mochi.tinytown import bills


def phase4_state():
    return {
        "residents": {
            "people": [
                {"id": 1, "street": "Elm", "arrears_cents": 0},
                {"id": 2, "street": "Elm", "arrears_cents": 600},
                {"id": 3, "street": "Oak", "arrears_cents": 150},
            ],
            "taxes_paid_cents": 1234,
            "bills_paid_cents": 180,
            "rent_paid_cents": 1800,
            "arrears_cents": 750,
            "in_arrears": 2,
        },
        "businesses": {
            "shops": {"tea": {"arrears_cents": 0}, "cart": {"arrears_cents": 800}},
            "taxes_paid_cents": {"tea": 40, "cart": 10},
            "bills_paid_cents": 400,
            "rent_paid_cents": 800,
            "arrears_cents": {"tea": 0, "cart": 800},
        },
    }


class TotalCentsTest(unittest.TestCase):
    def test_int_or_per_id_dict(self):
        self.assertEqual(bills.total_cents(1234), 1234)
        self.assertEqual(bills.total_cents({"tea": 40, "cart": 10}), 50)
        self.assertEqual(bills.total_cents({}), 0)

    def test_missing_or_malformed_is_none(self):
        for value in (None, "12", True, [1, 2], {"tea": "x"}, {"tea": False}, float("nan")):
            self.assertIsNone(bills.total_cents(value), value)


class SummaryTest(unittest.TestCase):
    def test_reads_every_phase4_key(self):
        self.assertEqual(
            bills.summary(phase4_state()),
            {
                "resident_taxes": 1234,
                "resident_bills": 180,
                "resident_rent": 1800,
                "resident_arrears": 750,
                "residents_behind": 2,
                "shop_taxes": 50,
                "shop_bills": 400,
                "shop_rent": 800,
                "shop_arrears": 800,
                "shops_behind": 1,
            },
        )

    def test_before_phase4_everything_is_none(self):
        state = {"residents": {"people": [{"id": 1}]}, "businesses": {"shops": {"tea": {}}}}
        self.assertEqual(set(bills.summary(state).values()), {None})
        self.assertEqual(set(bills.summary({}).values()), {None})

    def test_counts_fall_back_to_per_entity_keys(self):
        state = phase4_state()
        del state["residents"]["in_arrears"]
        del state["businesses"]["arrears_cents"]
        summary = bills.summary(state)
        self.assertEqual(summary["residents_behind"], 2)
        self.assertEqual(summary["shops_behind"], 1)
        self.assertIsNone(summary["shop_arrears"])

    def test_reading_never_mutates_state(self):
        state = phase4_state()
        before = copy.deepcopy(state)
        bills.summary(state)
        bills.shop_arrears(state)
        self.assertEqual(state, before)


class ReportedTest(unittest.TestCase):
    def test_false_before_phase4(self):
        self.assertFalse(bills.reported({}))
        self.assertFalse(bills.reported({"residents": {"people": [{"id": 1}]}, "businesses": {"shops": {"t": {}}}}))

    def test_any_single_key_counts(self):
        self.assertTrue(bills.reported({"businesses": {"rent_paid_cents": 0}}))
        self.assertTrue(bills.reported({"residents": {"in_arrears": 0}}))
        self.assertTrue(bills.reported({"residents": {"people": [{"arrears_cents": 0}]}}))
        self.assertTrue(bills.reported({"businesses": {"shops": {"t": {"arrears_cents": 0}}}}))


class PerEntityTest(unittest.TestCase):
    def test_person_arrears(self):
        self.assertEqual(bills.person_arrears({"arrears_cents": 600}), 600)
        self.assertIsNone(bills.person_arrears({"wallet_cents": 5}))
        self.assertIsNone(bills.person_arrears("nobody"))

    def test_shop_arrears_prefers_shop_key_then_per_shop_dict(self):
        state = phase4_state()
        state["businesses"]["shops"]["cart"] = {}
        self.assertEqual(bills.shop_arrears(state), {"tea": 0, "cart": 800})

    def test_shop_arrears_unknown_without_keys(self):
        state = {"businesses": {"shops": {"tea": {}}, "arrears_cents": 900}}
        self.assertEqual(bills.shop_arrears(state), {"tea": None})


if __name__ == "__main__":
    unittest.main()
