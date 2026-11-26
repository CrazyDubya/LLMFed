"""Tests for the CLI management tool."""

import os

import pytest

# Typer's rich-based --help renderer force-enables terminal colors whenever
# GITHUB_ACTIONS is set (true on every GitHub Actions runner), regardless of
# whether stdout is a real TTY. With color on, its option-name highlighter
# wraps each hyphen-separated segment of an option in its own ANSI escape
# span (e.g. "--narrative-retention" becomes several separately-colored
# pieces), which breaks a plain substring check for the option name even
# though nothing wrapped or changed visually. `_TYPER_FORCE_DISABLE_TERMINAL`
# is Typer's own documented escape hatch for exactly this. It's read once at
# import time by typer.rich_utils, so it must be set before typer (and
# anything importing it, like cli.main) is first imported.
os.environ["_TYPER_FORCE_DISABLE_TERMINAL"] = "1"

from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


@pytest.fixture
def replay_db(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models.db_models import Base
    from models.game_models import WorldDB
    from models.show_models import MatchDB
    import cli.main as cli_main

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        db.add(WorldDB(id="replay-world", name="Replay World"))
        db.add(MatchDB(id="replay-match", world_id="replay-world"))
        db.commit()
    monkeypatch.setattr(cli_main, "_get_db", session_factory)
    yield session_factory
    engine.dispose()


class TestMatchReplay:
    def test_events_in_tick_and_id_order(self, replay_db):
        from models.show_models import MatchEventDB

        with replay_db() as db:
            db.add_all([
                MatchEventDB(id=3, match_id="replay-match", tick=8,
                             event_type="finish", description="Winning pinfall."),
                MatchEventDB(id=2, match_id="replay-match", tick=2,
                             event_type="move", description="Follow-up suplex."),
                MatchEventDB(id=1, match_id="replay-match", tick=2,
                             event_type="move", description="Opening lockup."),
            ])
            db.commit()

        result = runner.invoke(app, ["match", "replay-match"])

        assert result.exit_code == 0
        assert "Play-by-Play:" in result.stdout
        assert "[  2] Opening lockup." in result.stdout
        assert "[  2] Follow-up suplex." in result.stdout
        assert "[  8] Winning pinfall." in result.stdout
        assert result.stdout.index("Opening lockup.") < result.stdout.index("Follow-up suplex.")
        assert result.stdout.index("Follow-up suplex.") < result.stdout.index("Winning pinfall.")

    def test_no_events(self, replay_db):
        result = runner.invoke(app, ["match", "replay-match"])

        assert result.exit_code == 0
        assert "Match Details" in result.stdout
        assert "Play-by-Play:" not in result.stdout

    def test_missing_match(self, replay_db):
        result = runner.invoke(app, ["match", "missing-match"])

        assert result.exit_code == 0
        assert "Match 'missing-match' not found." in result.stdout

    def test_query_error_is_not_hidden(self, replay_db, monkeypatch):
        from sqlalchemy.orm import Query
        from sqlalchemy.exc import OperationalError

        def fail_query(self):
            raise OperationalError("SELECT match_events", {}, RuntimeError("query failed"))

        monkeypatch.setattr(Query, "all", fail_query)

        result = runner.invoke(app, ["match", "replay-match"])

        assert result.exit_code != 0
        assert isinstance(result.exception, OperationalError)
        assert "No detailed play-by-play available." not in result.stdout


class TestFedRoster:
    def test_shows_wrestler_popularity(self, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models.db_models import Base
        from models.game_models import ContractDB, GameFederationDB, GameWrestlerDB, WorldDB
        import cli.main as cli_main

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        with session_factory() as db:
            world = WorldDB(name="Test World")
            federation = GameFederationDB(id="fed-1", world=world, name="Apex Wrestling")
            wrestler = GameWrestlerDB(
                world=world, name="Rook", real_name="Casey Vale", alignment="face", popularity=73,
            )
            db.add_all([federation, wrestler])
            db.flush()
            db.add(ContractDB(
                world_id=world.id, federation=federation, wrestler=wrestler, start_date="2026-01-01",
            ))
            db.commit()
        monkeypatch.setattr(cli_main, "_get_db", session_factory)

        result = runner.invoke(app, ["fed", "roster", "fed-1"], env={"COLUMNS": "100"})
        engine.dispose()

        assert result.exit_code == 0
        assert "Popularity" in result.stdout
        assert "Overall" not in result.stdout
        row = next(line for line in result.stdout.splitlines() if "Rook" in line)
        assert [cell.strip() for cell in row.split("│")[1:-1]] == ["Casey Vale", "Rook", "face", "73"]


class TestCLIExitCodes:
    def test_advance_missing_world(self, replay_db):
        result = runner.invoke(app, ["world", "advance", "missing-world"])

        assert result.exit_code == 1
        assert "not found" in result.stderr

    def test_import_missing_file(self, replay_db, tmp_path):
        result = runner.invoke(app, ["snapshot", "import", str(tmp_path / "missing.json")])

        assert result.exit_code == 1
        assert "No such file" in result.stderr

    @pytest.mark.parametrize("damage", ["truncated", "empty", "header", "checksum", "deflate"])
    def test_import_invalid_snapshot(self, replay_db, tmp_path, monkeypatch, damage):
        from unittest.mock import Mock
        import cli.main as cli_main
        from game_service.snapshot_service import create_snapshot
        from models.game_models import WorldDB

        with replay_db() as db:
            data = create_snapshot(db, world_id="replay-world")["data"]
        damaged = {
            "truncated": data[:20],
            "empty": b"",
            "header": b"not gzip",
            "checksum": data[:-8] + bytes([data[-8] ^ 255]) + data[-7:],
            "deflate": data[:10] + b"\x07" + data[11:],
        }
        path = tmp_path / "bad.gz"
        path.write_bytes(damaged[damage])
        db = replay_db()
        rollback = Mock(wraps=db.rollback)
        monkeypatch.setattr(db, "rollback", rollback)
        monkeypatch.setattr(cli_main, "_get_db", lambda: db)

        result = runner.invoke(app, ["snapshot", "import", str(path)], env={"COLUMNS": "240"})

        assert result.exit_code == 1
        assert f"Invalid or truncated snapshot: {path}" in result.stderr
        assert result.stdout == ""
        rollback.assert_called_once_with()
        with replay_db() as check:
            assert check.query(WorldDB).count() == 1

    def test_import_valid_snapshot(self, replay_db, tmp_path):
        from game_service.snapshot_service import create_snapshot
        from models.game_models import WorldDB

        with replay_db() as db:
            data = create_snapshot(db, world_id="replay-world")["data"]
        path = tmp_path / "valid.gz"
        path.write_bytes(data)

        result = runner.invoke(app, ["snapshot", "import", str(path)])

        assert result.exit_code == 0
        assert "Restored:" in result.stdout
        with replay_db() as db:
            assert db.query(WorldDB).count() == 2

    def test_import_overwrite_preserves_player_links(self, replay_db, tmp_path):
        from sqlalchemy import text
        from game_service.snapshot_service import create_snapshot
        from models.game_models import UserDB, PlayerDB, GameFederationDB

        with replay_db() as db:
            fed = GameFederationDB(world_id="replay-world", name="CLI Fed", short_name="CF")
            user = UserDB(email="cli@example.com", username="cli_promoter", password_hash="unused")
            db.add_all([fed, user])
            db.flush()
            player = PlayerDB(
                user_id=user.id, world_id="replay-world", player_type="promoter", federation_id=fed.id,
            )
            db.add(player)
            db.commit()
            old_fed_id = fed.id
            player_id = player.id
            data = create_snapshot(db, world_id="replay-world")["data"]

        path = tmp_path / "backup.gz"
        path.write_bytes(data)

        for _ in range(2):
            result = runner.invoke(app, ["snapshot", "import", str(path), "--target", "replay-world"])
            assert result.exit_code == 0
            assert "Restored:" in result.stdout
            with replay_db() as db:
                assert db.execute(text("PRAGMA foreign_key_check")).fetchall() == []
                restored_fed = db.query(GameFederationDB).filter_by(world_id="replay-world").one()
                restored_player = db.get(PlayerDB, player_id)
                assert restored_fed.id == old_fed_id
                assert restored_player.federation_id == restored_fed.id

    def test_export_missing_world(self, replay_db, tmp_path):
        result = runner.invoke(app, [
            "snapshot", "export", "missing-world", str(tmp_path / "snapshot.json"),
        ])

        assert result.exit_code == 1
        assert "not found" in result.stderr

    @pytest.mark.parametrize("command", [["world", "advance"], ["sim", "run"]])
    @pytest.mark.parametrize("days", ["0", "-3"])
    def test_nonpositive_days_rejected(self, replay_db, monkeypatch, command, days):
        from unittest.mock import Mock
        from game_service.world_ticker import WorldTicker

        tick = Mock(return_value={})
        monkeypatch.setattr(WorldTicker, "tick", tick)

        result = runner.invoke(app, [*command, "replay-world", "--days", days])

        assert result.exit_code == 2
        assert "Invalid value" in result.stderr
        tick.assert_not_called()

    @pytest.mark.parametrize("command", [["world", "advance"], ["sim", "run"]])
    def test_positive_days_advance(self, replay_db, command):
        from models.game_models import WorldDB

        with replay_db() as db:
            previous_tick = db.get(WorldDB, "replay-world").current_tick

        result = runner.invoke(app, [*command, "replay-world", "--days", "2"])

        assert result.exit_code == 0
        assert "Advanced 2 day(s)" in result.stdout
        with replay_db() as db:
            assert db.get(WorldDB, "replay-world").current_tick == previous_tick + 2


class TestCLIBasics:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "LLMFed" in result.stdout or "llmfed" in result.stdout

    def test_world_help(self):
        result = runner.invoke(app, ["world", "--help"])
        assert result.exit_code == 0
        assert "create" in result.stdout
        assert "list" in result.stdout

    def test_fed_help(self):
        result = runner.invoke(app, ["fed", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "roster" in result.stdout

    def test_sim_help(self):
        result = runner.invoke(app, ["sim", "--help"])
        assert result.exit_code == 0
        assert "run" in result.stdout
        assert "status" in result.stdout

    def test_init_command_exists(self):
        # Just verify the command is registered (don't actually run it)
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0

    def test_stats_command_exists(self):
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0

    def test_maintenance_command_exists(self):
        result = runner.invoke(app, ["maintenance", "--help"])
        assert result.exit_code == 0
        assert "narrative-retention" in result.stdout

    def test_match_command_exists(self):
        result = runner.invoke(app, ["match", "--help"])
        assert result.exit_code == 0


class TestFedList:
    def test_shows_federation_budget(self, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models.db_models import Base
        from models.game_models import WorldDB, GameFederationDB
        import cli.main as cli_main

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        with session_factory() as db:
            db.add(WorldDB(id="world-1", name="Test World"))
            db.add(GameFederationDB(
                id="fed-1", world_id="world-1", name="Apex Wrestling",
                budget=437431.41, prestige=72,
            ))
            db.commit()
        monkeypatch.setattr(cli_main, "_get_db", session_factory)

        result = runner.invoke(app, ["fed", "list", "world-1"])

        assert result.exit_code == 0
        assert "Apex Wrestling" in result.stdout
        assert "$437,431" in result.stdout
        assert "72" in result.stdout
        assert "$0" not in result.stdout
        assert "?" not in result.stdout
