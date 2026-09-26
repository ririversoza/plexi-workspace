import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import roster


ROSTER_PATH = Path(__file__).with_name("roster.json")


class RosterDataTests(unittest.TestCase):
    def test_roster_contains_all_eight_agents_and_required_fields(self):
        agents = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            [agent["name"] for agent in agents],
            ["Juniper", "Poppy", "Mochi", "Sora", "Kiwi", "Bao", "Nori", "Taro"],
        )
        self.assertTrue(
            all(
                set(agent)
                == {"name", "pronouns", "team", "role", "emoji", "catchphrase"}
                for agent in agents
            )
        )


class RosterCliTests(unittest.TestCase):
    def test_without_filter_prints_every_agent_as_a_table(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = roster.main([])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Name", output)
        self.assertIn("Team", output)
        for name in ("Juniper", "Poppy", "Mochi", "Sora", "Kiwi", "Bao", "Nori", "Taro"):
            self.assertIn(name, output)

    def test_team_filter_is_case_insensitive(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = roster.main(["--team", "cOdEx"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Kiwi", output)
        self.assertIn("Bao", output)
        self.assertNotIn("Mochi", output)
        self.assertNotIn("Taro", output)

    def test_unknown_team_prints_headers_without_agents(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = roster.main(["--team", "unknown"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Name", output)
        self.assertIn("Catchphrase", output)
        self.assertNotIn("Juniper", output)


if __name__ == "__main__":
    unittest.main()
