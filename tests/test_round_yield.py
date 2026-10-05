#!/usr/bin/env python3
"""Tests for the stopping-rule evaluator.

Run directly:

    python3 tests/test_round_yield.py
"""

from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "extended-adversarial-code-review"
    / "scripts"
    / "round_yield.py"
)
_spec = importlib.util.spec_from_file_location("round_yield", SCRIPT)
round_yield = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(round_yield)


def a_round(number, **overrides):
    """A round that fires nothing, so each test names its own cause."""
    entry = {
        "round": number,
        "claims": 20,
        "fixed": 10 + number,
        "user_visible": 5,
        "regressions": 0,
        "high_regressions": 0,
        "unbounded_domain": False,
        "shared_shape_ratio": 0.1,
    }
    entry.update(overrides)
    return entry


class Harness(unittest.TestCase):
    def run_cli(self, rounds, *extra, **record):
        payload = {"rounds": rounds}
        payload.update(record)
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        with handle:
            json.dump(payload, handle)
        output = io.StringIO()
        with redirect_stdout(output):
            code = round_yield.main([handle.name] + list(extra))
        return code, output.getvalue()


class TestClauseOneUnboundedDomain(Harness):
    """The earliest-firing clause, and the most valuable."""

    def test_an_unbounded_fix_domain_stops_the_loop(self):
        code, out = self.run_cli([a_round(1, unbounded_domain=True)])
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 1", out)
        self.assertIn("no enumeration", out)

    def test_it_fires_on_the_latest_round_only(self):
        # An earlier round whose domain was unbounded, since
        # redesigned, is not a reason to stop now.
        code, _ = self.run_cli(
            [a_round(1, unbounded_domain=True), a_round(2)]
        )
        self.assertEqual(code, round_yield.EXIT_CONTINUE)

    def test_omitting_it_is_reported_not_passed_over(self):
        # A clause nobody fed is not a clause that passed, and
        # this is the one people will leave out.
        entry = a_round(1)
        del entry["unbounded_domain"]
        code, out = self.run_cli([entry])
        self.assertEqual(code, round_yield.EXIT_CONTINUE)
        self.assertIn("not evaluated", out)
        self.assertIn("fire earliest", out)


class TestClauseTwoOneShape(Harness):
    def test_survivors_sharing_a_root_cause_stop_the_loop(self):
        code, out = self.run_cli([a_round(1, shared_shape_ratio=0.6)])
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 2", out)
        self.assertIn("60%", out)

    def test_below_the_threshold_is_quiet(self):
        code, _ = self.run_cli([a_round(1, shared_shape_ratio=0.59)])
        self.assertEqual(code, round_yield.EXIT_CONTINUE)

    def test_a_ratio_outside_the_range_is_refused(self):
        code, out = self.run_cli([a_round(1, shared_shape_ratio=60)])
        self.assertEqual(code, round_yield.EXIT_UNUSABLE)
        self.assertIn("0..1", out)


class TestClauseThreeSelfFeeding(Harness):
    def test_a_regression_from_an_earlier_round_stops_the_loop(self):
        code, out = self.run_cli(
            [a_round(1), a_round(2, regressions=1, high_regressions=1)]
        )
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 3", out)
        self.assertIn("reviewing itself", out)

    def test_a_regression_in_an_older_round_does_not(self):
        code, out = self.run_cli(
            [a_round(1, regressions=2, high_regressions=2), a_round(2)]
        )
        self.assertEqual(code, round_yield.EXIT_CONTINUE)
        self.assertIn("CONTINUE", out)


class TestClauseFourNetNegative(Harness):
    def test_a_round_over_a_quarter_cleanup_stops_the_loop(self):
        # 5 of 14 is 36%, the measured round-seven figure.
        code, out = self.run_cli([a_round(1, fixed=14, regressions=5)])
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 4", out)
        self.assertIn("36%", out)

    def test_a_round_at_the_threshold_does_not(self):
        # Exactly a quarter is allowed; the clause is "above".
        code, out = self.run_cli([a_round(1, fixed=8, regressions=2)])
        self.assertEqual(code, round_yield.EXIT_CONTINUE)
        self.assertNotIn("clause 4", out)

    def test_a_low_severity_regression_fires_four_but_not_three(self):
        code, out = self.run_cli([a_round(1, fixed=4, regressions=2)])
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 4", out)
        self.assertNotIn("clause 3:", out.split("STOP")[1])

    def test_without_the_high_count_clause_three_is_unevaluated(self):
        entry = a_round(1, regressions=1)
        del entry["high_regressions"]
        code, out = self.run_cli([entry])
        self.assertIn("not evaluated", out)
        self.assertIn("3", out.split("not evaluated")[1].split("\n")[0])

    def test_a_round_that_fixed_nothing_does_not_divide_by_zero(self):
        # The round stops on clause 8, not on clause 4 and not
        # on a ZeroDivisionError.
        code, out = self.run_cli([a_round(1, fixed=0, user_visible=0)])
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertNotIn("clause 4", out)
        self.assertIn("clause 8", out)


class TestClauseFiveFlatYield(Harness):
    def test_flat_fixed_yield_stops_the_loop(self):
        code, out = self.run_cli(
            [a_round(1, fixed=8), a_round(2, fixed=8), a_round(3, fixed=8)]
        )
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 5", out)

    def test_falling_fixed_yield_stops_the_loop(self):
        code, _ = self.run_cli(
            [a_round(1, fixed=12), a_round(2, fixed=9), a_round(3, fixed=4)]
        )
        self.assertEqual(code, round_yield.EXIT_STOP)

    def test_a_rising_round_clears_it(self):
        code, out = self.run_cli(
            [a_round(1, fixed=12), a_round(2, fixed=4), a_round(3, fixed=9)]
        )
        self.assertEqual(code, round_yield.EXIT_CONTINUE)
        self.assertIn("CONTINUE", out)

    def test_two_rounds_are_not_enough_to_judge_a_trend(self):
        code, _ = self.run_cli([a_round(1, fixed=9), a_round(2, fixed=8)])
        self.assertEqual(code, round_yield.EXIT_CONTINUE)


class TestClauseSixNothingVisible(Harness):
    def test_two_quiet_rounds_stop_the_loop(self):
        code, out = self.run_cli(
            [a_round(1), a_round(2, user_visible=0), a_round(3, user_visible=0)]
        )
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 6", out)

    def test_one_quiet_round_does_not(self):
        code, _ = self.run_cli([a_round(1), a_round(2, user_visible=0)])
        self.assertEqual(code, round_yield.EXIT_CONTINUE)

    def test_claims_without_user_visible_fixes_are_not_yield(self):
        code, out = self.run_cli(
            [
                a_round(1, claims=40, fixed=9, user_visible=0),
                a_round(2, claims=38, fixed=11, user_visible=0),
            ]
        )
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("Findings are not the same as defects", out)


class TestClauseSevenBudget(Harness):
    def test_passing_the_declared_ceiling_stops_the_loop(self):
        code, out = self.run_cli(
            [a_round(1, high_fixed=4, regressions=0, tokens=2_700_000)],
            token_ceiling_per_high=500_000,
        )
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 7", out)
        self.assertIn("675,000", out)

    def test_within_the_ceiling_is_quiet(self):
        code, _ = self.run_cli(
            [a_round(1, high_fixed=10, tokens=2_700_000)],
            token_ceiling_per_high=500_000,
        )
        self.assertEqual(code, round_yield.EXIT_CONTINUE)

    def test_self_inflicted_highs_do_not_count_as_yield(self):
        # Four highs fixed, all four caused by this loop, is
        # not four highs bought. Clause 3 fires as well; the
        # point is that clause 7 does not read it as progress.
        code, out = self.run_cli(
            [
                a_round(
                    1,
                    high_fixed=4,
                    regressions=4,
                    high_regressions=4,
                    fixed=8,
                    tokens=2_700_000,
                )
            ],
            token_ceiling_per_high=500_000,
        )
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 7", out)
        self.assertIn("this loop itself introduced", out)

    def test_no_declared_ceiling_leaves_the_clause_unevaluated(self):
        # Not declaring one is the defect the guidance names,
        # so it must be visible rather than silently skipped.
        code, out = self.run_cli([a_round(1, high_fixed=4, tokens=2_700_000)])
        self.assertEqual(code, round_yield.EXIT_CONTINUE)
        self.assertIn("not evaluated", out)
        self.assertIn("clause(s) 7", out)

    def test_a_round_without_tokens_leaves_the_budget_unevaluated(self):
        code, out = self.run_cli(
            [a_round(1, high_fixed=4, tokens=2_700_000), a_round(2, high_fixed=4)],
            "--explain",
            token_ceiling_per_high=500_000,
        )
        self.assertEqual(code, round_yield.EXIT_CONTINUE)
        self.assertIn("not evaluated", out)
        self.assertIn("tokens: not recorded for every round", out)
        self.assertNotIn("cost per user-visible", out)

    def test_a_recorded_zero_is_reported_as_zero(self):
        code, out = self.run_cli([a_round(1, tokens=0)], "--explain")
        self.assertIn("tokens: 0", out)
        self.assertNotIn("not recorded", out)


class TestClauseEightNothingFixed(Harness):
    """A review that hands findings back must still be able to stop.

    Clauses 4 to 6 read fix counts, so before clause 8 a round
    that raised findings and fixed none returned CONTINUE.
    """

    # The round-1 record from the agent run in which a
    # findings-only review had no clause it could stop on.
    FINDINGS_ONLY = {
        "round": 1,
        "claims": 4,
        "fixed": 0,
        "user_visible": 0,
        "regressions": 0,
        "unbounded_domain": False,
        "shared_shape_ratio": 0.33,
    }

    def test_the_findings_only_record_stops_on_clause_eight(self):
        code, out = self.run_cli([self.FINDINGS_ONLY])
        self.assertEqual(code, round_yield.EXIT_STOP)
        verdict = out.split("STOP")[1]
        self.assertIn("clause 8: round 1 applied no fixes (4 claims", verdict)
        self.assertIn("Hand the findings back", verdict)
        self.assertIn("another round would re-read unchanged code", verdict)
        self.assertIn("only after fixes land", verdict)
        for number in range(1, 8):
            self.assertNotIn("clause %d:" % number, verdict)

    def test_explain_reports_it_like_the_others(self):
        code, out = self.run_cli([self.FINDINGS_ONLY], "--explain")
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("  FIRED clause 8: the round applied no fixes", out)
        self.assertIn("  quiet clause 4: over a quarter of the round", out)

    def test_it_reads_the_latest_round_only(self):
        # Fixes landed after a findings-only round, so the code
        # changed and another round has something new to read.
        code, out = self.run_cli([a_round(1, fixed=0), a_round(2)])
        self.assertEqual(code, round_yield.EXIT_CONTINUE)
        self.assertNotIn("clause 8", out)

    def test_a_round_with_a_fix_is_quiet(self):
        code, out = self.run_cli(
            [a_round(1, fixed=1)], "--explain"
        )
        self.assertEqual(code, round_yield.EXIT_CONTINUE)
        self.assertIn("quiet clause 8", out)


class TestTheRecordMustBeUsable(Harness):
    def test_a_missing_count_is_refused_rather_than_guessed(self):
        code, out = self.run_cli([{"round": 1, "claims": 5, "fixed": 2}])
        self.assertEqual(code, round_yield.EXIT_UNUSABLE)
        self.assertIn("missing", out)

    def test_no_rounds_yet_is_not_a_verdict(self):
        code, out = self.run_cli([])
        self.assertEqual(code, round_yield.EXIT_UNUSABLE)
        self.assertIn("no rounds", out)

    def test_a_non_count_is_refused(self):
        code, out = self.run_cli([a_round(1, fixed="lots")])
        self.assertEqual(code, round_yield.EXIT_UNUSABLE)
        self.assertIn("non-count", out)

    def test_a_boolean_is_not_a_count(self):
        # bool is an int in Python, so this needs its own check
        # or "fixed": true reads as one defect fixed.
        code, out = self.run_cli([a_round(1, fixed=True)])
        self.assertEqual(code, round_yield.EXIT_UNUSABLE)
        self.assertIn("non-count", out)

    def test_a_negative_count_is_refused(self):
        code, out = self.run_cli([a_round(1, regressions=-1)])
        self.assertEqual(code, round_yield.EXIT_UNUSABLE)
        self.assertIn("negative", out)

    def test_unreadable_json_names_the_problem(self):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        with handle:
            handle.write("{not json")
        output = io.StringIO()
        with redirect_stdout(output):
            code = round_yield.main([handle.name])
        self.assertEqual(code, round_yield.EXIT_UNUSABLE)
        self.assertIn("not valid JSON", output.getvalue())

    def test_a_bare_array_is_accepted(self):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        with handle:
            json.dump([a_round(1)], handle)
        output = io.StringIO()
        with redirect_stdout(output):
            code = round_yield.main([handle.name])
        self.assertEqual(code, round_yield.EXIT_CONTINUE)


class TestTheExplainView(Harness):
    def test_it_prints_the_curve_every_clause_and_the_cost(self):
        code, out = self.run_cli(
            [
                a_round(1, tokens=2_700_000, minutes=35),
                a_round(2, tokens=2_700_000, minutes=36),
            ],
            "--explain",
        )
        self.assertEqual(code, round_yield.EXIT_CONTINUE)
        self.assertIn("yield curve", out)
        self.assertIn("5,400,000", out)
        self.assertIn("71 min", out)
        self.assertIn("cost per user-visible defect", out)
        for number in range(1, 9):
            self.assertIn("clause %d" % number, out)

    def test_an_unevaluated_clause_is_marked_distinctly(self):
        code, out = self.run_cli([a_round(1)], "--explain")
        self.assertEqual(code, round_yield.EXIT_CONTINUE)
        # Clause 7 has no ceiling here, so it is neither fired
        # nor quiet.
        self.assertIn("-----", out)

    def test_a_loop_that_fixed_nothing_visible_says_so(self):
        code, out = self.run_cli(
            [a_round(1, user_visible=0, tokens=2_700_000)], "--explain"
        )
        self.assertEqual(code, round_yield.EXIT_CONTINUE)
        self.assertIn("undefined", out)

    def test_the_stop_verdict_tells_the_agent_to_speak_up(self):
        # The failure this exists to prevent is a silent fifth
        # round, so the instruction belongs in the output.
        code, out = self.run_cli([a_round(1, regressions=1, high_regressions=1)])
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("Say this to the operator now", out)
        self.assertIn("Do not run another round first", out)


class TestAgainstTheMeasuredEpisode(Harness):
    """The numbers this tool was derived from.

    Counts are from the measurement report: claims raised,
    distinct defects fixed, user-visible fixes, tokens,
    minutes, and how many of those fixes were repairing an
    earlier fix in the same loop.

    `regressions` here is that last count at every severity.
    The report split out high-severity repairs only for round
    6, so only that row carries `high_regressions`, and clause
    3 is evaluated only there.
    """

    EPISODE = [
        {"round": 4, "claims": 40, "fixed": 17, "user_visible": 6,
         "regressions": 2, "unbounded_domain": True,
         "shared_shape_ratio": 0.4, "tokens": 2_757_427, "minutes": 35.3},
        {"round": 5, "claims": 40, "fixed": 23, "user_visible": 7,
         "regressions": 1, "unbounded_domain": True,
         "shared_shape_ratio": 0.65, "tokens": 2_772_379, "minutes": 36.1},
        {"round": 6, "claims": 45, "fixed": 14, "user_visible": 5,
         "regressions": 3, "high_regressions": 3, "unbounded_domain": True,
         "shared_shape_ratio": 0.65, "tokens": 2_633_390, "minutes": 41.6},
        {"round": 7, "claims": 37, "fixed": 14, "user_visible": 5,
         "regressions": 5, "unbounded_domain": True,
         "shared_shape_ratio": 0.65, "tokens": 2_746_818, "minutes": 31.2},
    ]

    def test_clause_one_would_have_stopped_it_at_round_four(self):
        # The earliest signal available, and the one that would
        # have saved the most: four rounds of the eight.
        code, out = self.run_cli(self.EPISODE[:1])
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 1", out)

    def test_clause_two_would_have_stopped_it_at_round_five(self):
        without_domain = []
        for entry in self.EPISODE[:2]:
            trimmed = dict(entry)
            del trimmed["unbounded_domain"]
            without_domain.append(trimmed)
        code, out = self.run_cli(without_domain)
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 2", out)

    def test_clause_three_fired_at_round_six(self):
        code, out = self.run_cli(self.EPISODE[:3])
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 3: round 6 fixed 3 high-severity", out)

    def test_round_seven_was_more_than_a_third_cleanup(self):
        code, out = self.run_cli(self.EPISODE)
        self.assertEqual(code, round_yield.EXIT_STOP)
        self.assertIn("clause 4", out)
        self.assertIn("36%", out)

    def test_the_full_episode_fires_everything_that_applies(self):
        code, out = self.run_cli(self.EPISODE, "--explain")
        self.assertEqual(code, round_yield.EXIT_STOP)
        for state in ("FIRED clause 1", "FIRED clause 2", "----- clause 3",
                      "FIRED clause 4", "FIRED clause 5"):
            self.assertIn(state, out)
        self.assertIn("not evaluated: clause(s) 3, 7", out)
        # It never went two rounds without a user-visible fix,
        # so clause 6 is listed and quiet rather than absent.
        self.assertIn("quiet clause 6", out)
        # And the ceiling was never declared, which is itself
        # the defect the guidance names.
        self.assertIn("----- clause 7", out)


class TestUnreadableInputIsUnusable(Harness):
    def test_a_file_that_is_not_utf8_is_unusable(self):
        handle = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        with handle:
            handle.write(b"\x89PNG\r\n\x1a\n\xff\xfe")
        output = io.StringIO()
        with redirect_stdout(output):
            code = round_yield.main([handle.name])
        self.assertEqual(code, round_yield.EXIT_UNUSABLE)
        self.assertIn("unusable record", output.getvalue())


class TestOptionalFieldsAreValidated(Harness):
    def test_a_non_count_optional_field_is_unusable(self):
        for field, value in (
            ("high_fixed", "two"),
            ("high_regressions", 1.0),
            ("shared_shape_ratio", True),
            ("tokens", "many"),
            ("introduced", 1.5),
            ("minutes", "ten"),
            ("unbounded_domain", "false"),
        ):
            overrides = {"tokens": 10, "high_fixed": 1}
            overrides[field] = value
            code, out = self.run_cli(
                [a_round(1, **overrides)],
                token_ceiling_per_high=1,
            )
            self.assertEqual(code, round_yield.EXIT_UNUSABLE, field)
            self.assertIn("unusable record", out)


if __name__ == "__main__":
    unittest.main()
