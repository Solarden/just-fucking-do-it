"""Tests for prediction, momentum, adaptive interval, and pacing."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from jfdi import service
from jfdi.models import ExercisePrediction


# ---------------------------------------------------------------------------
# ExercisePrediction.pacing_str
# ---------------------------------------------------------------------------


class TestPacingStr:
    def test_even_split(self):
        p = ExercisePrediction(
            name="pushups", done=0, goal=100, remaining=100,
            intervals_elapsed=0, intervals_left=10, intervals_total=10,
            projected_total=0, on_track=False,
            reps_per_set=10, bigger_sets=0, smaller_sets=10,
            momentum="no_data",
        )
        assert p.pacing_str == "10x10"

    def test_uneven_split(self):
        p = ExercisePrediction(
            name="pushups", done=5, goal=100, remaining=95,
            intervals_elapsed=1, intervals_left=9, intervals_total=10,
            projected_total=50, on_track=False,
            reps_per_set=10, bigger_sets=5, smaller_sets=4,
            momentum="no_data",
        )
        assert p.pacing_str == "5x11 + 4x10"

    def test_no_intervals_left(self):
        p = ExercisePrediction(
            name="pushups", done=50, goal=100, remaining=50,
            intervals_elapsed=10, intervals_left=0, intervals_total=10,
            projected_total=50, on_track=False,
            reps_per_set=50, bigger_sets=0, smaller_sets=0,
            momentum="no_data",
        )
        assert p.pacing_str == ""

    def test_complete(self):
        p = ExercisePrediction(
            name="pushups", done=100, goal=100, remaining=0,
            intervals_elapsed=5, intervals_left=5, intervals_total=10,
            projected_total=100, on_track=True,
            reps_per_set=0, bigger_sets=0, smaller_sets=0,
            momentum="steady",
        )
        assert p.pacing_str == ""

    def test_all_bigger_sets(self):
        """When remaining divides with remainder == intervals_left, all sets are bigger."""
        p = ExercisePrediction(
            name="pushups", done=97, goal=100, remaining=3,
            intervals_elapsed=7, intervals_left=3, intervals_total=10,
            projected_total=100, on_track=True,
            reps_per_set=1, bigger_sets=0, smaller_sets=3,
            momentum="steady",
        )
        assert p.pacing_str == "3x1"


# ---------------------------------------------------------------------------
# _compute_momentum
# ---------------------------------------------------------------------------


class TestMomentum:
    def test_too_few_sets(self):
        assert service._compute_momentum([10, 10]) == "no_data"
        assert service._compute_momentum([]) == "no_data"

    def test_steady(self):
        assert service._compute_momentum([10, 10, 10, 10]) == "steady"

    def test_accelerating(self):
        assert service._compute_momentum([5, 5, 10, 15]) == "accelerating"

    def test_decelerating(self):
        assert service._compute_momentum([15, 15, 5, 5]) == "decelerating"

    def test_from_zero_accelerating(self):
        assert service._compute_momentum([0, 0, 5, 10]) == "accelerating"

    def test_all_zeros(self):
        assert service._compute_momentum([0, 0, 0, 0]) == "no_data"

    def test_borderline_steady(self):
        """Exactly at the 1.1 / 0.9 boundary should be steady."""
        assert service._compute_momentum([10, 10, 10, 10, 10, 10]) == "steady"


# ---------------------------------------------------------------------------
# get_predictions
# ---------------------------------------------------------------------------


class TestGetPredictions:
    @patch("jfdi.service.datetime")
    def test_basic_prediction(self, mock_dt, temp_db):
        mock_dt.now.return_value = datetime(2026, 3, 16, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(10, 20)
        service.set_interval(60)
        service.log_set("pushups", 5)

        preds = service.get_predictions()
        pushups = next(p for p in preds if p.name == "pushups")

        assert pushups.intervals_total == 10
        assert pushups.intervals_elapsed == 2
        assert pushups.intervals_left == 8
        assert pushups.remaining == 95
        assert pushups.projected_total == round(5 / 2 * 10)  # 25
        assert pushups.on_track is False

    @patch("jfdi.service.datetime")
    def test_prediction_on_track(self, mock_dt, temp_db):
        mock_dt.now.return_value = datetime(2026, 3, 16, 15, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(10, 20)
        service.set_interval(60)
        service.log_set("pushups", 100)

        preds = service.get_predictions()
        pushups = next(p for p in preds if p.name == "pushups")

        assert pushups.on_track is True
        assert pushups.remaining == 0

    @patch("jfdi.service.datetime")
    def test_prediction_before_start(self, mock_dt, temp_db):
        mock_dt.now.return_value = datetime(2026, 3, 16, 7, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(10, 20)
        service.set_interval(60)

        preds = service.get_predictions()
        pushups = next(p for p in preds if p.name == "pushups")

        assert pushups.intervals_elapsed == 0
        assert pushups.intervals_left == 10

    @patch("jfdi.service.datetime")
    def test_pacing_distribution(self, mock_dt, temp_db):
        """95 remaining / 9 intervals = 10 base + 5 extra."""
        mock_dt.now.return_value = datetime(2026, 3, 16, 11, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(10, 20)
        service.set_interval(60)
        service.log_set("pushups", 5)

        preds = service.get_predictions()
        pushups = next(p for p in preds if p.name == "pushups")

        assert pushups.reps_per_set == 10
        assert pushups.bigger_sets == 5
        assert pushups.smaller_sets == 4
        total_paced = pushups.bigger_sets * (pushups.reps_per_set + 1) + pushups.smaller_sets * pushups.reps_per_set
        assert total_paced == 95


# ---------------------------------------------------------------------------
# get_adaptive_interval
# ---------------------------------------------------------------------------


class TestAdaptiveInterval:
    @patch("jfdi.service.datetime")
    def test_behind_pace_halves_interval(self, mock_dt, temp_db):
        mock_dt.now.return_value = datetime(2026, 3, 16, 18, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(8, 22)
        service.set_interval(30)

        adaptive = service.get_adaptive_interval()
        assert adaptive == 15  # 30 // 2

    @patch("jfdi.service.datetime")
    def test_on_pace_relaxes_slightly(self, mock_dt, temp_db):
        """Exactly on pace (ratio=1.0) earns a slight interval relaxation."""
        mock_dt.now.return_value = datetime(2026, 3, 16, 15, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(8, 22)
        service.set_interval(30)
        service.log_set("pushups", 50)
        service.log_set("crunches", 50)

        adaptive = service.get_adaptive_interval()
        assert adaptive == 45  # 1.5x base

    @patch("jfdi.service.datetime")
    def test_slightly_behind_keeps_interval(self, mock_dt, temp_db):
        """Slightly behind pace (ratio 0.5-1.0) keeps the base interval."""
        mock_dt.now.return_value = datetime(2026, 3, 16, 15, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(8, 22)
        service.set_interval(30)
        service.log_set("pushups", 30)
        service.log_set("crunches", 30)

        adaptive = service.get_adaptive_interval()
        assert adaptive == 30

    @patch("jfdi.service.datetime")
    def test_ahead_of_pace_relaxes_interval(self, mock_dt, temp_db):
        mock_dt.now.return_value = datetime(2026, 3, 16, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(8, 22)
        service.set_interval(30)
        service.log_set("pushups", 100)
        service.log_set("crunches", 100)

        adaptive = service.get_adaptive_interval()
        assert adaptive == 30  # all complete returns base

    @patch("jfdi.service.datetime")
    def test_floor_at_five_minutes(self, mock_dt, temp_db):
        mock_dt.now.return_value = datetime(2026, 3, 16, 20, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(8, 22)
        service.set_interval(8)

        adaptive = service.get_adaptive_interval()
        assert adaptive >= 5


# ---------------------------------------------------------------------------
# _time_pct_today
# ---------------------------------------------------------------------------


class TestTimePct:
    @patch("jfdi.service.datetime")
    def test_start_of_window(self, mock_dt, temp_db):
        mock_dt.now.return_value = datetime(2026, 3, 16, 8, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(8, 22)
        pct = service._time_pct_today()
        assert pct == 0.0

    @patch("jfdi.service.datetime")
    def test_mid_window(self, mock_dt, temp_db):
        mock_dt.now.return_value = datetime(2026, 3, 16, 15, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(8, 22)
        pct = service._time_pct_today()
        assert pct == pytest.approx(0.5, abs=0.01)

    @patch("jfdi.service.datetime")
    def test_end_of_window(self, mock_dt, temp_db):
        mock_dt.now.return_value = datetime(2026, 3, 16, 22, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(8, 22)
        pct = service._time_pct_today()
        assert pct == 1.0

    @patch("jfdi.service.datetime")
    def test_minute_precision(self, mock_dt, temp_db):
        """10:30 in an 8-22 window = 150min / 840min."""
        mock_dt.now.return_value = datetime(2026, 3, 16, 10, 30)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        service.set_quiet_hours(8, 22)
        pct = service._time_pct_today()
        assert pct == pytest.approx(150 / 840, abs=0.001)


# ---------------------------------------------------------------------------
# _sleep_until_tomorrow (bug fix verification)
# ---------------------------------------------------------------------------


class TestSleepUntilTomorrow:
    @patch("jfdi.daemon.time.sleep")
    @patch("jfdi.daemon.datetime")
    def test_month_boundary(self, mock_dt, mock_sleep):
        """Jan 31 should not crash."""
        from jfdi.daemon import _sleep_until_tomorrow

        mock_dt.now.return_value = datetime(2026, 1, 31, 23, 30)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        _sleep_until_tomorrow()

        mock_sleep.assert_called_once()
        sleep_secs = mock_sleep.call_args[0][0]
        assert sleep_secs >= 60
        assert sleep_secs < 2 * 3600

    @patch("jfdi.daemon.time.sleep")
    @patch("jfdi.daemon.datetime")
    def test_year_boundary(self, mock_dt, mock_sleep):
        """Dec 31 should not crash."""
        from jfdi.daemon import _sleep_until_tomorrow

        mock_dt.now.return_value = datetime(2026, 12, 31, 23, 50)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        _sleep_until_tomorrow()

        mock_sleep.assert_called_once()
        sleep_secs = mock_sleep.call_args[0][0]
        assert sleep_secs >= 60
