"""List IDs must be copyable into the corresponding detail commands."""

import pytest
from typer.testing import CliRunner

from cli.main import app


@pytest.fixture
def list_db(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models.db_models import Base
    from models.game_models import WorldDB, GameFederationDB, GameWrestlerDB, ContractDB
    import cli.main as cli_main

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        world = WorldDB(name="Copyable World")
        db.add(world)
        db.flush()
        fed = GameFederationDB(world_id=world.id, name="Copyable Wrestling")
        wrestler = GameWrestlerDB(world_id=world.id, name="Copyable Star")
        db.add_all([fed, wrestler])
        db.flush()
        db.add(ContractDB(world_id=world.id, federation_id=fed.id, wrestler_id=wrestler.id,
                          status="active", start_date="2026-01-01"))
        db.commit()
        ids = world.id, fed.id
    monkeypatch.setattr(cli_main, "_get_db", factory)
    monkeypatch.setenv("COLUMNS", "80")
    yield factory, ids
    engine.dispose()


def printed_id(output):
    return next(line.split("│")[1].strip() for line in output.splitlines()
                if line.startswith("│") and line.split("│")[1].strip() != "ID")


@pytest.mark.parametrize("kind", ["world", "fed"])
def test_list_id_round_trip(list_db, kind):
    _, (world_id, fed_id) = list_db
    runner = CliRunner()
    args = ["world", "list"] if kind == "world" else ["fed", "list", world_id]
    listed = runner.invoke(app, args)
    assert listed.exit_code == 0, listed.output
    identifier = printed_id(listed.stdout)
    command = ["world", "status"] if kind == "world" else ["fed", "roster"]
    detail = runner.invoke(app, [*command, identifier])
    assert detail.exit_code == 0, detail.output
    expected = "Copyable World" if kind == "world" else "Copyable Star"
    assert expected in detail.stdout, detail.stdout
    assert identifier == (world_id if kind == "world" else fed_id)
    assert max(map(len, listed.stdout.splitlines())) <= 80


@pytest.mark.parametrize("kind", ["world", "fed"])
def test_empty_list(list_db, kind):
    factory, (world_id, _) = list_db
    if kind == "world":
        from models.game_models import WorldDB
        with factory() as db:
            db.query(WorldDB).delete()
            db.commit()
    args = ["world", "list"] if kind == "world" else ["fed", "list", "missing-world"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0
    assert ("No worlds found" if kind == "world" else "No federations") in result.stdout


@pytest.mark.parametrize("kind", ["world", "fed"])
def test_list_query_error(list_db, monkeypatch, kind):
    from sqlalchemy.orm import Query
    from sqlalchemy.exc import OperationalError

    def fail_query(self):
        raise OperationalError("SELECT", {}, RuntimeError("query failed"))

    monkeypatch.setattr(Query, "all", fail_query)
    args = ["world", "list"] if kind == "world" else ["fed", "list", list_db[1][0]]
    result = CliRunner().invoke(app, args)
    assert result.exit_code != 0
    assert isinstance(result.exception, OperationalError)
