"""
Game API routes for LLMFed wrestling world.

Aggregator module that includes all game route sub-routers.
Each domain's endpoints are defined in api_gateway/routes/.
"""

from fastapi import APIRouter

from api_gateway.routes.auth_routes import router as auth_router
from api_gateway.routes.world_routes import router as world_router
from api_gateway.routes.federation_routes import router as federation_router
from api_gateway.routes.wrestler_routes import router as wrestler_router
from api_gateway.routes.booking_routes import router as booking_router
from api_gateway.routes.storyline_routes import router as storyline_router
from api_gateway.routes.stable_manager_routes import router as stable_manager_router
from api_gateway.routes.snapshot_routes import router as snapshot_router
from api_gateway.routes.analytics_routes import router as analytics_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(world_router)
router.include_router(federation_router)
router.include_router(wrestler_router)
router.include_router(booking_router)
router.include_router(storyline_router)
router.include_router(stable_manager_router)
router.include_router(snapshot_router)
router.include_router(analytics_router)
