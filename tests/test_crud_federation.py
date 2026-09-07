import pytest
import uuid
from agent_service.database import SessionLocal, init_db
from agent_service.crud import create_federation, get_federation_by_id, get_federations
from models.entities import FederationCreateData


@pytest.fixture(scope="module")
def db():
    init_db()
    db = SessionLocal()
    yield db
    db.close()


def test_create_get_federation(db):
    unique_name = f"Fed1_{uuid.uuid4().hex[:8]}"
    fed_data = FederationCreateData(
        name=unique_name, description="Desc", tier="independent", owner_user_id="owner1"
    )
    fed = create_federation(db, fed_data)
    assert fed is not None
    got = get_federation_by_id(db, fed.federation_id)
    assert got.federation_id == fed.federation_id
    all_feds = get_federations(db)
    assert any(f.federation_id == fed.federation_id for f in all_feds)
