from datetime import date

from sim.time import SimClock


def test_week_tick():
    clock = SimClock(date(2025, 9, 20), date(2025, 10, 20))
    clock.tick_week()
    assert clock.current == date(2025, 9, 27)
