"""Tests for the SkillCorner events adapter.

Aimed at the ways this adapter can be wrong while looking right, which is
how the four defects in the pose metrics survived thirty-three passing
tests: a fallback is exercised with the key present, a rate is counted as
a total, a threshold is read from the data it is meant to judge.

So each test here fails if the adapter goes back to the obvious-but-wrong
reading it was written to avoid.
"""

import collections
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adapter


def events(*rows):
    """Minimal event rows: only the columns the adapter reads."""
    blank = {
        "index": 0, "event_type": "", "event_subtype": "", "end_type": "",
        "player_id": "", "player_in_possession_id": "", "team_id": "1",
        "pass_outcome": "", "lead_to_shot": "", "lead_to_goal": "",
        "first_line_break": "", "second_last_line_break": "",
        "last_line_break": "",
    }
    out = []
    for i, row in enumerate(rows):
        merged = dict(blank)
        merged.update(row)
        merged["index"] = i
        out.append({k: str(v) for k, v in merged.items()})
    return out


def possession(player, end_type="", **kw):
    return dict(event_type="player_possession", player_id=player,
                end_type=end_type, **kw)


def engagement(player, end_type):
    return dict(event_type="on_ball_engagement", player_id=player,
                end_type=end_type)


SHEET = {
    7: {"player_id": 7, "name": "Siete", "role": "Center Midfield",
        "minutes": 90.0, "goals": 0.0, "team_id": 1, "team_name": "Club",
        "age": 25},
    9: {"player_id": 9, "name": "Nueve", "role": "Center Forward",
        "minutes": 90.0, "goals": 1.0, "team_id": 1, "team_name": "Club",
        "age": 28},
}
META = {"match_id": 1, "date": "2025-01-01", "teams": {1: "Club"},
        "home_score": 1, "away_score": 0}


class KeyPassesAndAssists(unittest.TestCase):
    """The pass before the shot, not every pass in the chain."""

    def test_only_the_pass_immediately_before_the_shot_counts(self):
        # Two completed passes then a shot. `lead_to_shot` would mark both;
        # only the second created it.
        rows = events(
            possession(7, "pass", pass_outcome="successful", lead_to_shot="True"),
            possession(7, "pass", pass_outcome="successful", lead_to_shot="True"),
            possession(9, "shot", lead_to_shot="True"),
        )
        key, _ = adapter.derive_pass_credits(rows)
        self.assertEqual(key[7], 1, "a chain of passes must yield one key pass")

    def test_a_player_is_not_credited_for_his_own_shot(self):
        rows = events(
            possession(9, "pass", pass_outcome="successful"),
            possession(9, "shot"),
        )
        key, _ = adapter.derive_pass_credits(rows)
        self.assertEqual(key[9], 0)

    def test_an_opponents_pass_is_not_an_assist(self):
        rows = events(
            dict(event_type="player_possession", player_id=4, team_id=2,
                 end_type="pass", pass_outcome="successful"),
            possession(9, "shot", lead_to_goal="True"),
        )
        key, assists = adapter.derive_pass_credits(rows)
        self.assertEqual(sum(key.values()), 0)
        self.assertEqual(sum(assists.values()), 0)

    def test_an_incomplete_pass_before_a_shot_is_not_a_key_pass(self):
        rows = events(
            possession(7, "pass", pass_outcome="unsuccessful"),
            possession(9, "shot"),
        )
        key, _ = adapter.derive_pass_credits(rows)
        self.assertEqual(sum(key.values()), 0)

    def test_assists_are_a_subset_of_key_passes(self):
        rows = events(
            possession(7, "pass", pass_outcome="successful"),
            possession(9, "shot", lead_to_goal="True"),
            possession(7, "pass", pass_outcome="successful"),
            possession(9, "shot"),
        )
        key, assists = adapter.derive_pass_credits(rows)
        self.assertEqual(key[7], 2)
        self.assertEqual(assists[7], 1)
        for pid in set(key) | set(assists):
            self.assertLessEqual(assists[pid], key[pid])

    def test_a_penalty_with_no_pass_before_it_credits_nobody(self):
        rows = events(possession(9, "shot", lead_to_goal="True"))
        _, assists = adapter.derive_pass_credits(rows)
        self.assertEqual(sum(assists.values()), 0)


class Interceptions(unittest.TestCase):
    """The field that looked like one was a pressure chain."""

    def test_an_indirect_regain_is_not_counted_as_anything(self):
        rows = events(
            engagement(7, "indirect_regain"),
            engagement(7, "indirect_regain"),
            engagement(7, "indirect_disruption"),
        )
        records = adapter.per_player_match(rows, SHEET, META)
        self.assertEqual(records[7]["tackles"], 0.0,
                         "indirect regains inflated the defensive term fourfold")
        self.assertNotIn("interceptions", records[7],
                         "interceptions have no counterpart and must stay absent")

    def test_a_direct_intervention_is_counted(self):
        rows = events(
            engagement(7, "direct_regain"),
            engagement(7, "direct_disruption"),
        )
        records = adapter.per_player_match(rows, SHEET, META)
        self.assertEqual(records[7]["tackles"], 2.0)

    def test_provenance_records_the_absence(self):
        self.assertEqual(adapter.PROVENANCE["interceptions"], "absent")
        self.assertEqual(adapter.PROVENANCE["tackles"], "estimated")
        self.assertEqual(adapter.PROVENANCE["goals"], "measured")


class Goals(unittest.TestCase):
    """From the sheet, never from the events."""

    def test_goals_come_from_the_sheet_even_with_no_shot_event(self):
        records = adapter.per_player_match(events(), SHEET, META)
        self.assertEqual(records[9]["goals"], 1.0)
        self.assertEqual(records[7]["goals"], 0.0)

    def test_a_scoring_shot_does_not_add_a_second_goal(self):
        rows = events(possession(9, "shot", lead_to_goal="True"))
        records = adapter.per_player_match(rows, SHEET, META)
        self.assertEqual(records[9]["goals"], 1.0)
        self.assertEqual(records[9]["shots"], 1.0)


class PassCompletion(unittest.TestCase):
    def test_completion_is_absent_rather_than_zero_when_no_pass_attempted(self):
        records = adapter.per_player_match(events(), SHEET, META)
        self.assertNotIn("pass_completion", records[7],
                         "a player who attempted no pass has no completion rate")

    def test_completion_is_the_ratio_of_the_sums_not_the_mean_of_ratios(self):
        # One match at 10/10 and one at 1/10 over equal minutes. The mean of
        # the rates is 0.55; the rate over the sample is 11/20 = 0.55 here by
        # coincidence, so weight the minutes differently to separate them.
        history = [
            {"minutes": 90.0, "pass_completion": 1.0},
            {"minutes": 10.0, "pass_completion": 0.0},
        ]
        weighted = adapter._weighted_completion(history)
        self.assertAlmostEqual(weighted, 0.9, places=3)
        self.assertNotAlmostEqual(weighted, 0.5, places=1,
                                  msg="the mean of rates lets a cameo "
                                      "outweigh a full match")


class Per90(unittest.TestCase):
    def test_a_rate_is_per_90_minutes_not_per_appearance(self):
        history = [{"minutes": 45.0, "shots": 1.0},
                   {"minutes": 45.0, "shots": 1.0}]
        self.assertAlmostEqual(adapter._per_90(history, "shots"), 2.0, places=3)

    def test_zero_minutes_yields_absence_not_division_by_zero(self):
        self.assertIsNone(adapter._per_90([{"minutes": 0.0, "shots": 3.0}], "shots"))


class Movement(unittest.TestCase):
    def test_movement_is_absent_unless_measured(self):
        metrics = adapter.build_metrics([{"minutes": 90.0, "shots": 1.0}])
        self.assertNotIn("movement", metrics)

    def test_movement_is_carried_when_measured(self):
        metrics = adapter.build_metrics(
            [{"minutes": 90.0, "shots": 1.0}],
            movement={"average_speed": 7.1, "distance_covered_per_90": 10400.0,
                      "high_intensity_runs": 41},
        )
        self.assertEqual(metrics["movement"]["average_speed"], 7.1)

    def test_an_empty_movement_dict_is_not_carried(self):
        metrics = adapter.build_metrics([{"minutes": 90.0}], movement={})
        self.assertNotIn("movement", metrics,
                         "an empty figure is an absent figure, not a present one")


class Age(unittest.TestCase):
    def test_age_is_taken_on_the_day_of_the_match(self):
        self.assertEqual(adapter._age_at("1996-09-04", "2024-12-21"), 28)
        self.assertEqual(adapter._age_at("1996-12-22", "2024-12-21"), 27,
                         "a birthday one day away must not have happened yet")

    def test_an_impossible_age_is_absent(self):
        self.assertIsNone(adapter._age_at("1900-01-01", "2024-12-21"))
        self.assertIsNone(adapter._age_at(None, "2024-12-21"))
        self.assertIsNone(adapter._age_at("1996-09-04", None))


class Sheet(unittest.TestCase):
    def test_a_named_substitute_who_did_not_play_is_not_an_appearance(self):
        raw = {
            "id": 1, "home_team_score": 0, "away_team_score": 0,
            "date_time": "2025-01-01T00:00:00",
            "home_team": {"id": 1, "name": "Club"},
            "away_team": {"id": 2, "name": "Otro"},
            "players": [
                {"id": 11, "short_name": "Jugo", "team_id": 1,
                 "player_role": {"name": "Center Midfield"}, "goal": 0,
                 "birthday": "1998-01-01",
                 "playing_time": {"total": {"minutes_played": 90.0}}},
                {"id": 12, "short_name": "Banca", "team_id": 1,
                 "player_role": {"name": "Substitute"}, "goal": 0,
                 "playing_time": {"total": {"minutes_played": 0}}},
                {"id": 13, "short_name": "Cero", "team_id": 1,
                 "player_role": {"name": "Center Forward"}, "goal": 0,
                 "playing_time": {"total": {"minutes_played": 0}}},
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(raw, f)
            path = f.name
        try:
            _meta, players = adapter.read_match_sheet(path)
        finally:
            os.unlink(path)
        self.assertEqual(set(players), {11},
                         "only the player who logged minutes played")

    def test_truthy_only_accepts_the_literal_string(self):
        self.assertTrue(adapter._truthy("True"))
        self.assertFalse(adapter._truthy("False"))
        self.assertFalse(adapter._truthy(""))
        self.assertFalse(adapter._truthy("true"),
                         "the CSV writes True; anything else is not a yes")


class Transfers(unittest.TestCase):
    """A season sample spans a transfer window."""

    def _moved(self):
        # Three at the selling club, then one at the buying club.
        return {
            7: {
                "player_id": 7, "name": "Siete",
                "roles": collections.Counter({"Center Midfield": 4}),
                "ages": [25],
                "appearances": [
                    {"date": "2025-01-01", "match_id": "1", "team": "Vende",
                     "role": "Center Midfield"},
                    {"date": "2025-01-08", "match_id": "2", "team": "Vende",
                     "role": "Center Midfield"},
                    {"date": "2025-01-15", "match_id": "3", "team": "Vende",
                     "role": "Center Midfield"},
                    {"date": "2025-03-01", "match_id": "4", "team": "Compra",
                     "role": "Center Midfield"},
                ],
                "history": [{"match_id": str(i), "date": f"2025-0{i}-01",
                             "minutes": 90.0} for i in range(1, 5)],
            }
        }

    def test_the_club_is_the_most_recent_not_the_most_frequent(self):
        player = self._moved()[7]
        self.assertEqual(adapter.latest_club(player), "Compra",
                         "listing a player at the club he left is the worst "
                         "field in a transfer product to get wrong")

    def test_the_payload_carries_him_at_his_new_club(self):
        payloads = adapter.build_payloads(self._moved(), min_matches=3)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["club"]["name"], "Compra")
        self.assertEqual(payloads[0]["players"][0]["current_team"], "Compra")

    def test_his_whole_history_travels_with_him(self):
        payloads = adapter.build_payloads(self._moved(), min_matches=3)
        self.assertEqual(len(payloads[0]["players"][0]["performance_history"]), 4,
                         "the matches he played before moving are still his")

    def test_a_club_with_no_name_is_not_invented(self):
        player = {"appearances": [{"date": "2025-01-01", "match_id": "1",
                                   "team": None, "role": "Center Midfield"}]}
        self.assertIsNone(adapter.latest_club(player))


class Roles(unittest.TestCase):
    def test_the_usual_role_wins_over_the_most_recent_one(self):
        player = {
            "roles": collections.Counter({"Center Back": 3, "Right Back": 1}),
            "appearances": [
                {"date": "2025-01-01", "match_id": "1", "role": "Center Back"},
                {"date": "2025-02-01", "match_id": "2", "role": "Right Back"},
            ],
        }
        self.assertEqual(adapter.usual_role(player), "Center Back")

    def test_a_tie_is_broken_by_recency_not_by_dict_order(self):
        player = {
            "roles": collections.Counter({"Left Winger": 2, "Right Winger": 2}),
            "appearances": [
                {"date": "2025-01-01", "match_id": "1", "role": "Left Winger"},
                {"date": "2025-02-01", "match_id": "2", "role": "Right Winger"},
            ],
        }
        self.assertEqual(adapter.usual_role(player), "Right Winger")
        # Same counts, reversed insertion order: the answer must not move.
        reversed_order = dict(player)
        reversed_order["roles"] = collections.Counter()
        reversed_order["roles"]["Right Winger"] = 2
        reversed_order["roles"]["Left Winger"] = 2
        self.assertEqual(adapter.usual_role(reversed_order), "Right Winger",
                         "the same input must not load two different positions")

    def test_no_role_at_all_yields_none(self):
        self.assertIsNone(adapter.usual_role({"roles": collections.Counter()}))


class Payloads(unittest.TestCase):
    def _players(self, n_matches):
        return {
            7: {"player_id": 7, "name": "Siete",
                "roles": collections.Counter({"Center Midfield": n_matches}),
                "appearances": [
                    {"date": f"2025-01-0{i+1}", "match_id": str(i),
                     "team": "Club", "role": "Center Midfield"}
                    for i in range(n_matches)
                ],
                "ages": [25],
                "history": [{"match_id": str(i), "date": f"2025-01-0{i+1}",
                             "minutes": 90.0, "shots": 1.0}
                            for i in range(n_matches)]},
        }

    def test_a_player_below_the_index_threshold_is_not_loaded(self):
        self.assertEqual(adapter.build_payloads(self._players(2), min_matches=3), [])

    def test_a_player_at_the_threshold_is_loaded(self):
        payloads = adapter.build_payloads(self._players(3), min_matches=3)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(len(payloads[0]["players"]), 1)

    def test_the_squad_lists_the_same_ids_as_the_players(self):
        payloads = adapter.build_payloads(self._players(3), min_matches=3)
        squad = payloads[0]["club"]["squad"]
        ids = [p["external_id"] for p in payloads[0]["players"]]
        self.assertEqual(sorted(squad), sorted(ids))

    def test_the_position_passed_on_is_the_providers_own_name(self):
        # Kumu's PROVIDER_GROUP_OVERRIDE is keyed on the raw name, so
        # normalising here would throw away the only thing it can match.
        payloads = adapter.build_payloads(self._players(3), min_matches=3)
        self.assertEqual(payloads[0]["players"][0]["position"], "Center Midfield")

    def test_no_index_is_supplied(self):
        # The schema says the index is derived, never supplied: it is
        # normalised across the whole population and this adapter sees one
        # league.
        payloads = adapter.build_payloads(self._players(3), min_matches=3)
        self.assertNotIn("performance_index", payloads[0]["players"][0])


class Layout(unittest.TestCase):
    """Both shapes of the release read the same."""

    def _write_match(self, folder, match_id):
        os.makedirs(folder, exist_ok=True)
        sheet = {
            "id": match_id, "home_team_score": 0, "away_team_score": 0,
            "date_time": "2025-01-01T00:00:00",
            "home_team": {"id": 1, "name": "Club"},
            "away_team": {"id": 2, "name": "Otro"},
            "players": [{
                "id": 11, "short_name": "Jugo", "team_id": 1,
                "player_role": {"name": "Center Midfield"}, "goal": 0,
                "birthday": "1998-01-01",
                "playing_time": {"total": {"minutes_played": 90.0}},
            }],
        }
        with open(os.path.join(folder, f"{match_id}_match.json"), "w") as f:
            json.dump(sheet, f)
        header = ["index", "event_type", "event_subtype", "end_type",
                  "player_id", "player_in_possession_id", "team_id",
                  "pass_outcome", "lead_to_shot", "lead_to_goal",
                  "first_line_break", "second_last_line_break",
                  "last_line_break"]
        with open(os.path.join(folder, f"{match_id}_dynamic_events.csv"), "w") as f:
            f.write(",".join(header) + "\n")
            f.write("0,player_possession,,pass,11,,1,successful,,,,,\n")

    def test_nested_and_flat_layouts_agree(self):
        with tempfile.TemporaryDirectory() as root:
            nested = os.path.join(root, "nested")
            flat = os.path.join(root, "flat")
            os.makedirs(flat)
            for match_id in ("100", "200"):
                self._write_match(os.path.join(nested, match_id), match_id)
                self._write_match(flat, match_id)
            self.assertEqual(len(adapter.find_matches(nested)), 2)
            self.assertEqual(len(adapter.find_matches(flat)), 2)
            self.assertEqual(
                adapter.read_release(nested).keys(),
                adapter.read_release(flat).keys(),
            )

    def test_a_match_missing_its_events_is_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            self._write_match(root, "300")
            os.unlink(os.path.join(root, "300_dynamic_events.csv"))
            self.assertEqual(adapter.find_matches(root), [],
                             "half a match is not a match")


if __name__ == "__main__":
    unittest.main(verbosity=2)
