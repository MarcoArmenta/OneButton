"""Turn raw key down/up into clean button events, tolerant of tremor.

Pure and time-explicit so it is testable. Three filters, all in the config:

- min_hold:   a press shorter than this is a tremor tap and is ignored.
- bounce:     a release followed by a new press within this window is the same
              hold continuing (a trembling hand loses contact for a moment).
- refractory: after an event is emitted, presses in this window are ignored,
              so a double tap cannot start and stop a recording at once.
- long_hold:  held this long counts as a long press, emitted as soon as it is
              reached so the user feels it without waiting for the release.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SHORT, LONG = "short", "long"


@dataclass
class PressFilter:
    min_hold: float = 0.06
    bounce: float = 0.15
    refractory: float = 0.35
    long_hold: float = 1.5
    _down_at: float | None = None      # start of the current hold (survives bounces)
    _up_at: float | None = None        # last release, while inside the bounce window
    _long_sent: bool = False
    _last_event_at: float = field(default=-1e9)

    def down(self, t: float) -> list[tuple[str, float]]:
        if self._down_at is None:
            if t - self._last_event_at < self.refractory:
                return []
            self._down_at, self._long_sent = t, False
        self._up_at = None  # a re-press inside the bounce window continues the hold
        return []

    def up(self, t: float) -> list[tuple[str, float]]:
        if self._down_at is not None and self._up_at is None:
            self._up_at = t
        return []

    def tick(self, t: float) -> list[tuple[str, float]]:
        """Call often (every ~20 ms). Returns emitted events as (kind, time)."""
        if self._down_at is None:
            return []
        if not self._long_sent and (self._up_at is None) and t - self._down_at >= self.long_hold:
            self._long_sent = True
            self._last_event_at = t
            return [(LONG, t)]
        if self._up_at is not None and t - self._up_at >= self.bounce:
            held = self._up_at - self._down_at
            self._down_at, up = None, self._up_at
            self._up_at = None
            if self._long_sent:
                return []
            if held < self.min_hold:
                return []
            self._last_event_at = up
            return [(LONG if held >= self.long_hold else SHORT, up)]
        return []
