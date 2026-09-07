"""Stable and manager routes: stable CRUD, manager CRUD, manager bonds."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from agent_service.database import get_db
from api_gateway.security import get_current_user, TokenData
from models.game_schemas import (
    ManagerCreate,
    ManagerResponse,
    ManagerClientCreate,
    ManagerClientResponse,
    StableCreate,
    StableResponse,
    StableMemberResponse,
    StableAddMember,
    StableUpdate,
)
from models.game_models import (
    GameWrestlerDB,
    ContractDB,
    StableDB,
)
from game_service.world_service import get_world
from game_service import stable_service, manager_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game-stable-manager"])


def _handle_value_error(e: ValueError):
    raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Managers & Valets
# ---------------------------------------------------------------------------


@router.get("/worlds/{world_id}/managers", response_model=List[ManagerResponse])
async def api_list_managers(
    world_id: str,
    federation_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all managers in a world."""
    managers = manager_service.list_managers(db, world_id, federation_id)
    return [ManagerResponse.model_validate(m) for m in managers]


@router.post(
    "/worlds/{world_id}/managers", response_model=ManagerResponse, status_code=201
)
async def api_create_manager(
    world_id: str,
    data: ManagerCreate,
    federation_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new manager character."""
    try:
        mgr = manager_service.create_manager(
            db,
            world_id,
            name=data.name,
            alignment=data.alignment,
            archetype=data.archetype,
            federation_id=federation_id,
            real_name=data.real_name,
            gender=data.gender,
            personality_traits=data.personality_traits,
            catchphrase=data.catchphrase,
        )
        return ManagerResponse.model_validate(mgr)
    except ValueError as e:
        _handle_value_error(e)


@router.get("/worlds/{world_id}/manager-bonds")
async def api_list_manager_bonds(
    world_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all manager-client bonds in a world."""
    bonds = manager_service.list_manager_bonds(db, world_id)
    results = []
    for item in bonds:
        bond = item["bond"]
        resp = ManagerClientResponse.model_validate(bond)
        resp.manager_name = item["manager_name"]
        resp.client_name = item["client_name"]
        results.append(resp)
    return results


@router.post(
    "/worlds/{world_id}/manager-bonds",
    response_model=ManagerClientResponse,
    status_code=201,
)
async def api_assign_manager(
    world_id: str,
    data: ManagerClientCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Assign a manager to a wrestler client."""
    try:
        world = get_world(db, world_id)
        if not world:
            raise HTTPException(status_code=404, detail="World not found")
        bond = manager_service.assign_manager(
            db,
            world_id,
            manager_id=data.manager_id,
            client_wrestler_id=data.client_wrestler_id,
            role=data.role,
            specialization=data.specialization,
            game_date=world.current_game_date,
        )
        return ManagerClientResponse.model_validate(bond)
    except ValueError as e:
        _handle_value_error(e)


@router.delete("/manager-bonds/{bond_id}", status_code=204)
async def api_remove_manager_bond(
    bond_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """End a manager-client relationship."""
    if not manager_service.remove_manager(db, bond_id):
        raise HTTPException(status_code=404, detail="Bond not found")


@router.post("/managers/{manager_id}/promo")
async def api_manager_promo(
    manager_id: str,
    client_wrestler_id: str,
    target_wrestler_id: Optional[str] = None,
    promo_type: str = "in_ring",
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a promo where a manager speaks on behalf of their client."""
    result = manager_service.generate_manager_promo(
        db, manager_id, client_wrestler_id, target_wrestler_id, promo_type
    )
    if not result["content"]:
        raise HTTPException(status_code=404, detail="Manager or client not found")
    return result


# ---------------------------------------------------------------------------
# Stables / Factions
# ---------------------------------------------------------------------------


@router.get("/worlds/{world_id}/stables", response_model=List[StableResponse])
async def api_list_stables(
    world_id: str,
    federation_id: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active stables in a world."""
    stables = stable_service.list_stables(db, world_id, federation_id)
    results = []
    for s in stables:
        data = stable_service.get_stable_with_members(db, s.id)
        resp = StableResponse.model_validate(s)
        resp.manager_name = data.get("manager_name")
        resp.members = [StableMemberResponse(**m) for m in data.get("members", [])]
        results.append(resp)
    return results


@router.post(
    "/worlds/{world_id}/stables", response_model=StableResponse, status_code=201
)
async def api_create_stable(
    world_id: str,
    data: StableCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new stable/faction."""
    try:
        # Determine federation from the leader wrestler's contract
        leader = db.query(GameWrestlerDB).filter_by(id=data.leader_id).first()
        if not leader:
            raise HTTPException(status_code=404, detail="Leader wrestler not found")
        contract = (
            db.query(ContractDB)
            .filter_by(wrestler_id=data.leader_id, status="active")
            .first()
        )
        fed_id = contract.federation_id if contract else None
        if not fed_id:
            raise HTTPException(status_code=400, detail="Leader has no active contract")

        world = get_world(db, world_id)
        stable = stable_service.create_stable(
            db,
            world_id,
            fed_id,
            name=data.name,
            leader_id=data.leader_id,
            founding_member_ids=data.founding_member_ids,
            alignment=data.alignment,
            short_name=data.short_name,
            catchphrase=data.catchphrase,
            group_finisher_name=data.group_finisher_name,
            manager_id=data.manager_id,
            game_date=world.current_game_date if world else None,
        )
        detail = stable_service.get_stable_with_members(db, stable.id)
        resp = StableResponse.model_validate(stable)
        resp.manager_name = detail.get("manager_name")
        resp.members = [StableMemberResponse(**m) for m in detail.get("members", [])]
        return resp
    except ValueError as e:
        _handle_value_error(e)


@router.get("/stables/{stable_id}", response_model=StableResponse)
async def api_get_stable(
    stable_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a stable with its members."""
    data = stable_service.get_stable_with_members(db, stable_id)
    if not data:
        raise HTTPException(status_code=404, detail="Stable not found")
    stable = data["stable"]
    resp = StableResponse.model_validate(stable)
    resp.manager_name = data.get("manager_name")
    resp.members = [StableMemberResponse(**m) for m in data.get("members", [])]
    return resp


@router.post("/stables/{stable_id}/members", status_code=201)
async def api_add_stable_member(
    stable_id: str,
    data: StableAddMember,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a wrestler to a stable."""
    stable = db.query(StableDB).filter_by(id=stable_id, is_active=True).first()
    if not stable:
        raise HTTPException(status_code=404, detail="Stable not found")
    world = get_world(db, stable.world_id)
    member = stable_service.add_member(
        db,
        stable_id,
        data.wrestler_id,
        data.role,
        game_date=world.current_game_date if world else None,
    )
    return {"id": member.id, "wrestler_id": member.wrestler_id, "role": member.role}


@router.delete("/stables/{stable_id}/members/{wrestler_id}", status_code=204)
async def api_remove_stable_member(
    stable_id: str,
    wrestler_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a wrestler from a stable."""
    stable = db.query(StableDB).filter_by(id=stable_id, is_active=True).first()
    if not stable:
        raise HTTPException(status_code=404, detail="Stable not found")
    world = get_world(db, stable.world_id)
    if not stable_service.remove_member(
        db,
        stable_id,
        wrestler_id,
        game_date=world.current_game_date if world else None,
    ):
        raise HTTPException(status_code=404, detail="Member not found")


@router.patch("/stables/{stable_id}", response_model=StableResponse)
async def api_update_stable(
    stable_id: str,
    data: StableUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a stable's details."""
    stable = db.query(StableDB).filter_by(id=stable_id, is_active=True).first()
    if not stable:
        raise HTTPException(status_code=404, detail="Stable not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(stable, field, value)
    db.commit()
    detail = stable_service.get_stable_with_members(db, stable.id)
    resp = StableResponse.model_validate(stable)
    resp.manager_name = detail.get("manager_name")
    resp.members = [StableMemberResponse(**m) for m in detail.get("members", [])]
    return resp
