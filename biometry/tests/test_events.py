"""Ordered motion events — the IF-C2-to-Driver payload."""
import numpy as np
import pytest

from engine.events import DOWN, MOVE, UP, compile_path, compile_tap, events_to_dicts
from models.gesture import GestureDistortionSynthesizer


def test_a_tap_is_down_then_up_at_the_same_point():
    ev = compile_tap(120.5, 340.0)
    assert [e.kind for e in ev] == [DOWN, UP]
    assert (ev[0].x, ev[0].y) == (ev[1].x, ev[1].y) == (120.5, 340.0)
    assert ev[1].t_ms > ev[0].t_ms == 0.0


def test_a_path_compiles_to_down_moves_up_in_order():
    g = GestureDistortionSynthesizer(rng=np.random.default_rng(2))
    r = g.synthesize(100, 800, 900, 800, 0.5)
    ev = compile_path(r["path"])
    assert ev[0].kind == DOWN and ev[-1].kind == UP
    assert all(e.kind == MOVE for e in ev[1:-1])
    times = [e.t_ms for e in ev]
    assert times == sorted(times)
    assert len(ev) == len(r["path"])


def test_events_are_coordinates_never_element_references():
    ev = compile_tap(10, 20) + compile_path([(0, 0, 0), (5, 5, 10)])
    for d in events_to_dicts(ev):
        assert set(d) == {"kind", "x", "y", "t_ms"}


def test_out_of_order_timestamps_are_rejected():
    with pytest.raises(ValueError):
        compile_path([(0, 0, 10.0), (5, 5, 5.0)])


def test_a_single_point_is_not_a_gesture():
    with pytest.raises(ValueError):
        compile_path([(0, 0, 0.0)])
