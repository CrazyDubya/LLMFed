import pytest
import pytest_asyncio
import uuid
from agent_service.database import AsyncSessionLocal, init_db
from agent_service.crud import create_federation, get_federation_by_id, get_federations
from models.entities import FederationCreateData


@pytest_asyncio.fixture
async def db():
    await init_db()
    async with AsyncSessionLocal() as session:
        yield session


@pytest.mark.asyncio
async def test_create_get_federation(db):
    unique_name = f"Fed1_{uuid.uuid4().hex[:8]}"
    fed_data = FederationCreateData(
        name=unique_name,
        description="Desc",
        tier="independent",
        owner_user_id="owner1"
    )
    fed = await create_federation(db, fed_data)
    assert fed is not None
    got = await get_federation_by_id(db, fed.federation_id)
    assert got.federation_id == fed.federation_id
    all_feds = await get_federations(db)
    assert any(f.federation_id == fed.federation_id for f in all_feds)
