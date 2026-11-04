"""Unit tests for the entry point: flags, plan validation and exit codes."""

import unittest

from run import build_plan, parse_args


class ParseArgsTest(unittest.TestCase):

    def test_defaults_match_the_documented_timer(self):
        args = parse_args([])
        self.assertEqual(8765, args.port)
        self.assertEqual(25.0, args.focus)
        self.assertEqual(5.0, args.short_break)
        self.assertEqual(15.0, args.long_break)
        self.assertEqual(4, args.cycle)

    def test_fractional_minutes_are_accepted_as_flags(self):
        args = parse_args(["--focus", "0.05", "--cycle", "2"])
        self.assertEqual(0.05, args.focus)
        self.assertEqual(2, args.cycle)


class BuildPlanTest(unittest.TestCase):

    def test_flags_become_a_validated_plan_in_seconds(self):
        plan = build_plan(parse_args([]))
        self.assertEqual(25 * 60, plan.focus_seconds)
        self.assertEqual(5 * 60, plan.short_break_seconds)
        self.assertEqual(15 * 60, plan.long_break_seconds)
        self.assertEqual(4, plan.cycle_length)

    def test_bad_flag_values_raise_before_a_socket_opens(self):
        with self.assertRaises(ValueError):
            build_plan(parse_args(["--focus", "0"]))
        with self.assertRaises(ValueError):
            build_plan(parse_args(["--cycle", "0"]))
        with self.assertRaises(ValueError):
            build_plan(parse_args(["--focus", "-5"]))


if __name__ == "__main__":
    unittest.main()
