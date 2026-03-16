"""Tests for the service layer -- the core business logic."""

import pytest

from jfdi import service


class TestLogSet:
    def test_log_basic(self, temp_db):
        progress = service.log_set("pushups", 20)
        assert progress.name == "pushups"
        assert progress.done == 20
        assert progress.goal == 100
        assert progress.sets == [20]

    def test_log_accumulates(self, temp_db):
        service.log_set("pushups", 20)
        progress = service.log_set("pushups", 15)
        assert progress.done == 35
        assert progress.sets == [20, 15]

    def test_log_via_alias(self, temp_db):
        progress = service.log_set("p", 25)
        assert progress.name == "pushups"
        assert progress.done == 25

    def test_log_unknown_exercise(self, temp_db):
        with pytest.raises(ValueError, match="Unknown exercise"):
            service.log_set("swimming", 10)

    def test_log_zero_reps(self, temp_db):
        with pytest.raises(ValueError, match="positive"):
            service.log_set("pushups", 0)

    def test_log_negative_reps(self, temp_db):
        with pytest.raises(ValueError, match="positive"):
            service.log_set("pushups", -5)


class TestUndo:
    def test_undo_basic(self, temp_db):
        service.log_set("pushups", 20)
        result = service.undo_last()
        assert "20" in result
        assert "pushups" in result

    def test_undo_empty(self, temp_db):
        result = service.undo_last()
        assert "Nothing" in result

    def test_undo_removes_from_total(self, temp_db):
        service.log_set("pushups", 20)
        service.log_set("pushups", 15)
        service.undo_last()
        status = service.get_status()
        pushups = next(e for e in status.exercises if e.name == "pushups")
        assert pushups.done == 20


class TestStatus:
    def test_status_empty(self, temp_db):
        status = service.get_status()
        assert len(status.exercises) == 2
        assert all(e.done == 0 for e in status.exercises)
        assert status.all_complete is False

    def test_status_partial(self, temp_db):
        service.log_set("pushups", 50)
        status = service.get_status()
        pushups = next(e for e in status.exercises if e.name == "pushups")
        assert pushups.done == 50
        assert status.all_complete is False

    def test_status_complete(self, temp_db):
        service.log_set("pushups", 100)
        service.log_set("crunches", 100)
        status = service.get_status()
        assert status.all_complete is True


class TestConfig:
    def test_get_config(self, temp_db):
        cfg = service.get_config()
        assert cfg.interval_minutes == 30
        assert cfg.sound_enabled is True
        assert "pushups" in cfg.exercises
        assert "crunches" in cfg.exercises

    def test_set_interval(self, temp_db):
        service.set_interval(15)
        cfg = service.get_config()
        assert cfg.interval_minutes == 15

    def test_set_interval_invalid(self, temp_db):
        with pytest.raises(ValueError):
            service.set_interval(0)

    def test_set_sound(self, temp_db):
        service.set_sound(False)
        cfg = service.get_config()
        assert cfg.sound_enabled is False

    def test_quiet_hours(self, temp_db):
        service.set_quiet_hours(9, 21)
        cfg = service.get_config()
        assert cfg.quiet_hours_start == 9
        assert cfg.quiet_hours_end == 21

    def test_quiet_hours_invalid(self, temp_db):
        with pytest.raises(ValueError):
            service.set_quiet_hours(-1, 25)


class TestExerciseManagement:
    def test_add_exercise(self, temp_db):
        service.add_exercise("burpees", 50)
        cfg = service.get_config()
        assert "burpees" in cfg.exercises
        assert cfg.exercises["burpees"] == 50

    def test_remove_exercise(self, temp_db):
        service.remove_exercise("pushups")
        cfg = service.get_config()
        assert "pushups" not in cfg.exercises

    def test_remove_nonexistent(self, temp_db):
        with pytest.raises(ValueError, match="No active exercise"):
            service.remove_exercise("yoga")


class TestAliases:
    def test_resolve_default_alias(self, temp_db):
        assert service.resolve_alias("p") == "pushups"
        assert service.resolve_alias("c") == "crunches"

    def test_resolve_unknown_returns_input(self, temp_db):
        assert service.resolve_alias("xyz") == "xyz"

    def test_set_alias(self, temp_db):
        service.set_alias("pushups", "pu")
        assert service.resolve_alias("pu") == "pushups"

    def test_set_alias_unknown_exercise(self, temp_db):
        with pytest.raises(ValueError, match="Unknown exercise"):
            service.set_alias("swimming", "s")

    def test_remove_alias(self, temp_db):
        service.remove_alias("p")
        assert service.resolve_alias("p") == "p"


class TestMessages:
    def test_list_messages(self, temp_db):
        messages = service.list_messages()
        assert len(messages) > 0

    def test_list_by_category(self, temp_db):
        quotes = service.list_messages("quote")
        assert all(m.category == "quote" for m in quotes)

    def test_add_message(self, temp_db):
        msg = service.add_message("Test message", "nudge")
        assert msg.text == "Test message"
        assert msg.category == "nudge"
        assert msg.is_builtin is False

    def test_add_invalid_category(self, temp_db):
        with pytest.raises(ValueError, match="Category must be"):
            service.add_message("Bad", "invalid")

    def test_remove_message(self, temp_db):
        msg = service.add_message("Delete me", "quote")
        service.remove_message(msg.id)
        messages = service.list_messages()
        assert msg.id not in {m.id for m in messages}

    def test_get_random_message(self, temp_db):
        msg = service.get_random_message("quote")
        assert isinstance(msg, str)
        assert len(msg) > 0


class TestSounds:
    def test_list_sounds_empty(self, temp_db):
        sounds = service.list_sounds()
        assert sounds == []

    def test_add_sound_file_not_found(self, temp_db):
        with pytest.raises(ValueError, match="File not found"):
            service.add_sound("test", "/nonexistent/file.mp3")


class TestExport:
    def test_export_csv(self, temp_db):
        service.log_set("pushups", 20)
        path = service.export_history(fmt="csv")
        assert path.endswith(".csv")

    def test_export_json(self, temp_db):
        service.log_set("pushups", 20)
        path = service.export_history(fmt="json")
        assert path.endswith(".json")


class TestEscalation:
    def test_escalation_no_exercises(self, temp_db):
        service.remove_exercise("pushups")
        service.remove_exercise("crunches")
        level = service.get_escalation_level()
        assert level == "friendly"

    def test_escalation_all_complete(self, temp_db):
        service.log_set("pushups", 100)
        service.log_set("crunches", 100)
        level = service.get_escalation_level()
        assert level == "friendly"


class TestDaemonManagement:
    def test_daemon_not_running(self, temp_db):
        assert service.is_daemon_running() is False

    def test_get_daemon_pid_none(self, temp_db):
        assert service.get_daemon_pid() is None

    def test_save_and_clear_pid(self, temp_db):
        service.save_daemon_pid(99999)
        assert service.get_daemon_pid() == 99999
        service.clear_daemon_pid()
        assert service.get_daemon_pid() is None
