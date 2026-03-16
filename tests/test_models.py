"""Tests for model dataclasses."""

from jfdi.models import ExerciseProgress


class TestExerciseProgress:
    def test_remaining(self):
        ep = ExerciseProgress(name="pushups", done=40, goal=100, sets=[20, 20])
        assert ep.remaining == 60

    def test_remaining_when_over(self):
        ep = ExerciseProgress(name="pushups", done=120, goal=100)
        assert ep.remaining == 0

    def test_complete(self):
        assert ExerciseProgress(name="x", done=100, goal=100).complete is True
        assert ExerciseProgress(name="x", done=99, goal=100).complete is False
        assert ExerciseProgress(name="x", done=150, goal=100).complete is True

    def test_pct(self):
        ep = ExerciseProgress(name="x", done=50, goal=100)
        assert ep.pct == 50.0

    def test_pct_capped_at_100(self):
        ep = ExerciseProgress(name="x", done=200, goal=100)
        assert ep.pct == 100.0

    def test_pct_zero_goal(self):
        ep = ExerciseProgress(name="x", done=0, goal=0)
        assert ep.pct == 100.0
