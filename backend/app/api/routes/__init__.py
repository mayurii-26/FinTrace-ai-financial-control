from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.exceptions import router as exceptions_router
from app.api.routes.investigation import router as investigation_router  # legacy /api/investigation
from app.api.routes.investigate import router as investigate_router      # /api/exceptions/{id}/investigate
from app.api.routes.action import router as action_router                # /api/exceptions/{id}/action
from app.api.routes.verify import router as verify_router                # /api/exceptions/{id}/verify
from app.api.routes.reconciliation import router as reconciliation_router
from app.api.routes.benchmark import router as benchmark_router
from app.api.routes.transactions import router as transactions_router
from app.api.routes.lifecycle import router as lifecycle_router
from app.api.routes.audit import router as audit_router

__all__ = [
    "dashboard_router",
    "exceptions_router",
    "investigation_router",
    "investigate_router",
    "action_router",
    "verify_router",
    "reconciliation_router",
    "benchmark_router",
    "transactions_router",
    "lifecycle_router",
    "audit_router",
]
