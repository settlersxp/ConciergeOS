from app.routes.reservations import router as reservations_router
from app.routes.guest_search import router as guest_search_router
from app.routes.settings import router as settings_router
from app.routes.performance_testing import router as performance_testing_router
from app.routes.prompts import router as prompts_router
from app.routes.models import router as models_router

__all__ = [
    "reservations_router",
    "guest_search_router",
    "settings_router",
    "performance_testing_router",
    "prompts_router",
    "models_router",
]
