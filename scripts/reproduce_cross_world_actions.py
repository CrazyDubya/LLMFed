"""Run with PYTHONPATH=. OTEL_SDK_DISABLED=true .venv/bin/python scripts/reproduce_cross_world_actions.py."""

import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_service.database import get_db_sync
from api_gateway.main import app
from api_gateway.security import TokenData, get_current_user
from game_service.world_ticker import WorldTicker
from models.game_models import Base, ContractDB, GameWrestlerDB, WrestlerStatsDB, UserDB


def main():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        db.add(UserDB(id="evidence-user", email="evidence@example.test", username="evidence", password_hash="unused"))
        db.commit()
        app.dependency_overrides[get_db_sync] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: TokenData(user_id="evidence-user")
        try:
            with TestClient(app, base_url="http://localhost") as client:
                worlds = [client.post("/game/worlds", json={"name": name}).json() for name in ("A", "B")]
                a, b = [w["id"] for w in worlds]
                player_response = client.post("/game/players", json={
                    "world_id": b, "player_type": "promoter", "federation_name": "Evidence B",
                })
                assert player_response.status_code == 201, player_response.text
                federation = player_response.json()["federation_id"]
                free_agents = db.query(GameWrestlerDB).filter(
                    GameWrestlerDB.world_id == a,
                    ~GameWrestlerDB.id.in_(db.query(ContractDB.wrestler_id).filter_by(status="active")),
                ).limit(2).all()
                assert len(free_agents) == 2
                trainee, agent = free_agents
                stats = db.query(WrestlerStatsDB).filter_by(wrestler_id=trainee.id).one()
                stats.power = 57
                db.commit()

                def state():
                    return {
                        "train": {"world": "A" if trainee.world_id == a else "B", "power": stats.power},
                        "sign": {"world": "A" if agent.world_id == a else "B", "contracts": [
                            {"world": "B" if c.world_id == b else "A", "status": c.status}
                            for c in db.query(ContractDB).filter_by(wrestler_id=agent.id).all()
                        ]},
                    }

                print("BEFORE", json.dumps(state(), sort_keys=True))
                for kind, data in [
                    ("train", {"wrestler_id": trainee.id, "stat": "power"}),
                    ("sign_wrestler", {"wrestler_id": agent.id, "federation_id": federation}),
                ]:
                    response = client.post(f"/game/worlds/{b}/actions", json={
                        "action_type": kind, "action_data": data,
                    })
                    print("QUEUE", kind, response.status_code, response.json().get("message", "accepted"))
                WorldTicker(db, b)._process_player_actions()
                db.commit()
                db.expire_all()
                actions = client.get(f"/game/worlds/{b}/actions").json()
                print("PROCESSED", json.dumps([{k: item[k] for k in ("action_type", "status", "result")}
                                               for item in actions], sort_keys=True))
                print("AFTER", json.dumps(state(), sort_keys=True))
        finally:
            app.dependency_overrides.clear()
    engine.dispose()


if __name__ == "__main__":
    main()
