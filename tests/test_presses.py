import unittest

from onebutton.presses import LONG, SHORT, PressFilter


def run(f, script):
    """script: list of (t, 'down'|'up'); ticks every 10 ms up to the end + 1 s. Returns event kinds."""
    events = []
    t, i, end = 0.0, 0, script[-1][0] + 1.0
    while t <= end + 1e-9:
        while i < len(script) and script[i][0] <= t + 1e-9:
            getattr(f, script[i][1])(script[i][0])
            i += 1
        events += [k for k, _ in f.tick(t)]
        t = round(t + 0.01, 4)
    return events


class PressFilterTests(unittest.TestCase):
    def test_clean_short_and_long(self):
        self.assertEqual(run(PressFilter(), [(0, "down"), (0.2, "up")]), [SHORT])
        self.assertEqual(run(PressFilter(), [(0, "down"), (2.0, "up")]), [LONG])

    def test_long_fires_at_threshold_not_release(self):
        f = PressFilter()
        f.down(0.0)
        self.assertEqual([k for k, _ in f.tick(1.49)], [])
        self.assertEqual([k for k, _ in f.tick(1.5)], [LONG])
        f.up(3.0)
        self.assertEqual(run(f, [(3.0, "up")]), [])

    def test_a_very_short_press_counts(self):
        # No minimum length unless one is asked for: a quick tap is a press like any other.
        self.assertEqual(run(PressFilter(), [(0, "down"), (0.03, "up")]), [SHORT])
        self.assertEqual(run(PressFilter(), [(0, "down"), (0.005, "up")]), [SHORT])

    def test_a_minimum_length_can_still_be_asked_for(self):
        self.assertEqual(run(PressFilter(min_hold=0.06), [(0, "down"), (0.03, "up")]), [])
        self.assertEqual(run(PressFilter(min_hold=0.06), [(0, "down"), (0.08, "up")]), [SHORT])

    def test_bounce_inside_a_hold_is_one_long(self):
        script = [(0, "down"), (0.5, "up"), (0.55, "down"), (1.0, "up"), (1.08, "down"), (2.0, "up")]
        self.assertEqual(run(PressFilter(), script), [LONG])

    def test_double_tap_is_one_short(self):
        self.assertEqual(run(PressFilter(), [(0, "down"), (0.15, "up"), (0.4, "down"), (0.55, "up")]), [SHORT])

    def test_two_deliberate_presses(self):
        self.assertEqual(run(PressFilter(), [(0, "down"), (0.2, "up"), (1.0, "down"), (1.2, "up")]), [SHORT, SHORT])

    def test_configurable(self):
        f = PressFilter(min_hold=0.2, long_hold=1.0)
        self.assertEqual(run(f, [(0, "down"), (0.15, "up")]), [])
        self.assertEqual(run(PressFilter(min_hold=0.2, long_hold=1.0), [(0, "down"), (1.1, "up")]), [LONG])


class DefaultsTests(unittest.TestCase):
    """Out of the box no press is too short to count; the setting stays for whoever needs it."""

    def test_no_minimum_length_by_default(self):
        import yaml
        from pathlib import Path

        from onebutton import config

        self.assertEqual(config.DEFAULTS["press_min_hold"], 0)
        example = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.example.yaml").read_text(encoding="utf-8"))
        self.assertEqual(example["press_min_hold"], 0, "the installer copies this file into local/config.yaml")
        self.assertEqual(PressFilter().min_hold, 0)


if __name__ == "__main__":
    unittest.main()
