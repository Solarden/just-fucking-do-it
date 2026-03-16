"""Tests for the database layer."""

from jfdi import db


class TestSchema:
    def test_init_creates_tables(self, temp_db):
        with db.get_conn() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = {r[0] for r in tables}
        assert "exercises" in table_names
        assert "logs" in table_names
        assert "config" in table_names
        assert "messages" in table_names
        assert "sounds" in table_names

    def test_default_exercises_seeded(self, temp_db):
        with db.get_conn() as conn:
            exercises = db.get_active_exercises(conn)
        names = {e["name"] for e in exercises}
        assert "pushups" in names
        assert "crunches" in names

    def test_default_config_seeded(self, temp_db):
        with db.get_conn() as conn:
            val = db.get_config_value(conn, "interval")
        assert val == "30"

    def test_default_messages_seeded(self, temp_db):
        with db.get_conn() as conn:
            messages = db.get_messages(conn)
        assert len(messages) > 0
        categories = {m["category"] for m in messages}
        assert "quote" in categories
        assert "nudge" in categories
        assert "completion" in categories

    def test_default_aliases_seeded(self, temp_db):
        with db.get_conn() as conn:
            aliases = db.get_aliases(conn)
        assert aliases.get("p") == "pushups"
        assert aliases.get("c") == "crunches"


class TestExercises:
    def test_add_and_get(self, temp_db):
        with db.get_conn() as conn:
            db.add_exercise(conn, "burpees", 50)
            ex = db.get_exercise_by_name(conn, "burpees")
        assert ex is not None
        assert ex["daily_goal"] == 50

    def test_deactivate(self, temp_db):
        with db.get_conn() as conn:
            assert db.deactivate_exercise(conn, "pushups") is True
            active = db.get_active_exercises(conn)
        names = {e["name"] for e in active}
        assert "pushups" not in names


class TestLogs:
    def test_insert_and_get_total(self, temp_db):
        with db.get_conn() as conn:
            ex = db.get_exercise_by_name(conn, "pushups")
            db.insert_log(conn, ex["id"], 20)
            db.insert_log(conn, ex["id"], 15)
            total = db.get_today_total(conn, ex["id"])
        assert total == 35

    def test_delete_last(self, temp_db):
        with db.get_conn() as conn:
            ex = db.get_exercise_by_name(conn, "pushups")
            db.insert_log(conn, ex["id"], 10)
            db.insert_log(conn, ex["id"], 20)
            deleted = db.delete_last_log(conn)
        assert deleted is not None
        assert deleted["reps"] == 20

    def test_delete_last_empty(self, temp_db):
        with db.get_conn() as conn:
            deleted = db.delete_last_log(conn)
        assert deleted is None


class TestConfig:
    def test_set_and_get(self, temp_db):
        with db.get_conn() as conn:
            db.set_config_value(conn, "test_key", "test_val")
            val = db.get_config_value(conn, "test_key")
        assert val == "test_val"

    def test_delete(self, temp_db):
        with db.get_conn() as conn:
            db.set_config_value(conn, "del_me", "yes")
            assert db.delete_config_key(conn, "del_me") is True
            assert db.get_config_value(conn, "del_me") is None


class TestMessages:
    def test_insert_and_list(self, temp_db):
        with db.get_conn() as conn:
            msg_id = db.insert_message(conn, "Test nudge", "nudge")
            msgs = db.get_messages(conn, "nudge")
        texts = {m["text"] for m in msgs}
        assert "Test nudge" in texts

    def test_delete(self, temp_db):
        with db.get_conn() as conn:
            msg_id = db.insert_message(conn, "Bye", "quote")
            assert db.delete_message(conn, msg_id) is True
            assert db.delete_message(conn, msg_id) is False

    def test_random(self, temp_db):
        with db.get_conn() as conn:
            msg = db.get_random_message(conn, "quote")
        assert msg is not None
