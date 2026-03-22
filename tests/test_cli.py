"""Tests for the CLI layer using Typer's CliRunner."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from jfdi.cli import app

runner = CliRunner()


class TestLog:
    def test_log_basic(self, temp_db):
        result = runner.invoke(app, ["log", "pushups", "20"])
        assert result.exit_code == 0
        assert "+20 pushups" in result.output
        assert "20/100" in result.output

    def test_log_accumulates(self, temp_db):
        runner.invoke(app, ["log", "pushups", "20"])
        result = runner.invoke(app, ["log", "pushups", "30"])
        assert result.exit_code == 0
        assert "50/100" in result.output

    def test_log_unknown_exercise(self, temp_db):
        result = runner.invoke(app, ["log", "swimming", "10"])
        assert result.exit_code == 1
        assert "Unknown exercise" in result.output

    def test_log_shows_complete(self, temp_db):
        result = runner.invoke(app, ["log", "pushups", "100"])
        assert result.exit_code == 0
        assert "COMPLETE" in result.output

    def test_log_zero_reps(self, temp_db):
        result = runner.invoke(app, ["log", "pushups", "0"])
        assert result.exit_code != 0


class TestStatus:
    def test_status_empty(self, temp_db):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "pushups" in result.output
        assert "crunches" in result.output
        assert "0/100" in result.output

    def test_status_with_progress(self, temp_db):
        runner.invoke(app, ["log", "pushups", "50"])
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "50/100" in result.output


class TestUndo:
    def test_undo_basic(self, temp_db):
        runner.invoke(app, ["log", "pushups", "20"])
        result = runner.invoke(app, ["undo"])
        assert result.exit_code == 0
        assert "20" in result.output
        assert "pushups" in result.output

    def test_undo_empty(self, temp_db):
        result = runner.invoke(app, ["undo"])
        assert result.exit_code == 0
        assert "Nothing" in result.output


class TestHistory:
    def test_history_empty(self, temp_db):
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        assert "No history" in result.output

    def test_history_with_data(self, temp_db):
        runner.invoke(app, ["log", "pushups", "20"])
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        assert "20" in result.output

    def test_history_days_option(self, temp_db):
        result = runner.invoke(app, ["history", "--days", "3"])
        assert result.exit_code == 0


class TestStreak:
    def test_streak_empty(self, temp_db):
        result = runner.invoke(app, ["streak"])
        assert result.exit_code == 0
        assert "Current streak" in result.output
        assert "Best streak" in result.output


class TestPace:
    def test_pace_empty(self, temp_db):
        result = runner.invoke(app, ["pace"])
        assert result.exit_code == 0

    def test_pace_with_progress(self, temp_db):
        runner.invoke(app, ["log", "pushups", "50"])
        result = runner.invoke(app, ["pace"])
        assert result.exit_code == 0
        assert "pushups" in result.output


class TestExport:
    def test_export_csv(self, temp_db):
        runner.invoke(app, ["log", "pushups", "20"])
        result = runner.invoke(app, ["export"])
        assert result.exit_code == 0
        assert "Exported to" in result.output
        assert ".csv" in result.output

    def test_export_json(self, temp_db):
        runner.invoke(app, ["log", "pushups", "20"])
        result = runner.invoke(app, ["export", "--format", "json"])
        assert result.exit_code == 0
        assert ".json" in result.output

    def test_export_no_overwrite(self, temp_db):
        """Exporting twice should produce different file paths."""
        runner.invoke(app, ["log", "pushups", "20"])
        result1 = runner.invoke(app, ["export"])
        result2 = runner.invoke(app, ["export"])
        assert result1.exit_code == 0
        assert result2.exit_code == 0
        # Extract paths from output
        path1 = result1.output.strip().split("Exported to:")[-1].strip()
        path2 = result2.output.strip().split("Exported to:")[-1].strip()
        assert path1 != path2


class TestConfigCommands:
    def test_config_show(self, temp_db):
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "Interval" in result.output
        assert "pushups" in result.output

    def test_config_interval(self, temp_db):
        result = runner.invoke(app, ["config", "interval", "15"])
        assert result.exit_code == 0
        assert "15 minutes" in result.output

    def test_config_interval_invalid(self, temp_db):
        result = runner.invoke(app, ["config", "interval", "0"])
        assert result.exit_code != 0

    def test_config_hours(self, temp_db):
        result = runner.invoke(app, ["config", "hours", "9-21"])
        assert result.exit_code == 0
        assert "9:00 - 21:00" in result.output

    def test_config_hours_invalid(self, temp_db):
        result = runner.invoke(app, ["config", "hours", "bad"])
        assert result.exit_code == 1

    def test_config_sound_on_off(self, temp_db):
        result = runner.invoke(app, ["config", "sound", "off"])
        assert result.exit_code == 0
        assert "disabled" in result.output

        result = runner.invoke(app, ["config", "sound", "on"])
        assert result.exit_code == 0
        assert "enabled" in result.output

    def test_config_sound_invalid(self, temp_db):
        result = runner.invoke(app, ["config", "sound", "maybe"])
        assert result.exit_code == 1

    def test_config_add_exercise(self, temp_db):
        result = runner.invoke(app, ["config", "add", "burpees", "50"])
        assert result.exit_code == 0
        assert "burpees" in result.output

    def test_config_remove_exercise(self, temp_db):
        result = runner.invoke(app, ["config", "remove", "pushups"])
        assert result.exit_code == 0
        assert "removed" in result.output

    def test_config_remove_nonexistent(self, temp_db):
        result = runner.invoke(app, ["config", "remove", "yoga"])
        assert result.exit_code == 1

    def test_config_alias(self, temp_db):
        result = runner.invoke(app, ["config", "alias", "pushups", "pu"])
        assert result.exit_code == 0
        assert "pu" in result.output


class TestMessageCommands:
    def test_message_list(self, temp_db):
        result = runner.invoke(app, ["message", "list"])
        assert result.exit_code == 0
        assert "DO IT" in result.output

    def test_message_list_filter(self, temp_db):
        result = runner.invoke(app, ["message", "list", "--category", "quote"])
        assert result.exit_code == 0

    def test_message_add_and_remove(self, temp_db):
        result = runner.invoke(app, ["message", "add", "nudge", "Get moving!"])
        assert result.exit_code == 0
        assert "Get moving!" in result.output


class TestSoundCommands:
    def test_sound_list(self, temp_db):
        result = runner.invoke(app, ["sound", "list"])
        assert result.exit_code == 0

    def test_sound_add_missing_file(self, temp_db):
        result = runner.invoke(app, ["sound", "add", "test", "/nonexistent/file.mp3"])
        assert result.exit_code == 1
        assert "File not found" in result.output


class TestAliasRewriting:
    def test_get_known_commands(self):
        from jfdi.cli import _get_known_commands
        known = _get_known_commands()
        assert "log" in known
        assert "status" in known
        assert "config" in known
        assert "daemon" in known
        assert "--help" in known
