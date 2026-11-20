"""Run against a checkout: python scripts/repro_championship_scope.py --repo PATH --label NAME."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    database = Path.home() / f"championship-{args.label}-{time.time_ns()}.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{database}"
    os.environ["OTEL_SDK_DISABLED"] = "true"
    sys.path.insert(0, str(repo))
    from agent_service.database import init_db_sync, SessionLocal
    from api_gateway.security import create_access_token
    from game_service.world_ticker import advance_game_date
    from models.game_models import UserDB, ChampionshipDB, GameWrestlerDB

    init_db_sync()
    with SessionLocal() as db:
        user = UserDB(username="scope-evidence", email="scope@example.test", password_hash="unused")
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id})

    log_path = Path.home() / f"championship-{args.label}-uvicorn.log"
    with log_path.open("w") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api_gateway.main:app", "--host", "127.0.0.1", "--port", "8097"],
            cwd=repo, env=os.environ.copy(), stdout=log, stderr=log,
        )
        try:
            with httpx.Client(base_url="http://127.0.0.1:8097", timeout=120,
                              headers={"Authorization": f"Bearer {token}"}) as client:
                for _ in range(100):
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    if server.poll() is not None:
                        raise RuntimeError(f"Server exited; see {log_path}")
                    time.sleep(0.1)

                def post(path, payload):
                    response = client.post(path, json=payload)
                    response.raise_for_status()
                    return response.json()

                world_a = post("/game/worlds", {"name": "World A"})
                world_b = post("/game/worlds", {"name": "World B"})
                player = post("/game/players", {"world_id": world_b["id"], "player_type": "promoter",
                                                "federation_name": "World B Promotion"})
                show = post(f"/game/federations/{player['federation_id']}/shows",
                            {"name": "Scope Show", "game_date": advance_game_date(world_b["current_game_date"])})
                with SessionLocal() as db:
                    title = db.query(ChampionshipDB).filter_by(world_id=world_a["id"]).first()
                    title_id, old_holder = title.id, title.current_holder_id
                    wrestlers = db.query(GameWrestlerDB).filter_by(world_id=world_b["id"]).limit(2).all()
                    participants = [w.id for w in wrestlers]
                response = client.post(f"/game/shows/{show['id']}/matches", json={
                    "participant_ids": participants, "is_title_match": True,
                    "championship_id": title_id, "planned_winner_id": participants[0],
                })
                print(f"{args.label}: cross-world booking HTTP {response.status_code}")
                if response.status_code == 201:
                    tick = client.post(f"/game/worlds/{world_b['id']}/tick")
                    with SessionLocal() as db:
                        holder = db.get(ChampionshipDB, title_id).current_holder_id
                    print(f"{args.label}: tick HTTP {tick.status_code}; A title moved to B wrestler: "
                          f"{holder in participants and holder != old_holder}")
                else:
                    print(f"{args.label}: {response.json()}")
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
