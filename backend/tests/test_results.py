"""Equivalent grade uses the event's passing_reference_percent (not a fixed scale)."""

import pytest

from app.services.results import compute_equivalent_grade


class TestComputeEquivalentGrade:
    def test_passing_threshold_maps_to_four(self):
        assert compute_equivalent_grade(60, 60) == pytest.approx(4.0)
        assert compute_equivalent_grade(80, 80) == pytest.approx(4.0)

    def test_perfect_score_maps_to_seven(self):
        assert compute_equivalent_grade(100, 60) == pytest.approx(7.0)

    def test_zero_score_maps_to_one(self):
        assert compute_equivalent_grade(0, 60) == pytest.approx(1.0)

    def test_stricter_passing_percent_changes_grade_for_same_score(self):
        # Same raw percentage, different passing threshold per ECOE.
        lenient = compute_equivalent_grade(70, 60)
        strict = compute_equivalent_grade(70, 80)
        assert lenient > 4.0
        assert strict < 4.0
        assert lenient != strict

    def test_below_passing_is_piecewise_linear(self):
        # Halfway to the passing point should sit halfway between 1.0 and 4.0.
        assert compute_equivalent_grade(30, 60) == pytest.approx(2.5)
