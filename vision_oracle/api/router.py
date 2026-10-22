"""
Master API router mounting all modular route collections.
"""

from fastapi import APIRouter

from vision_oracle.api.routes_status import router as status_router
from vision_oracle.api.routes_evaluate import router as evaluate_router
from vision_oracle.api.routes_trigger import router as trigger_router
from vision_oracle.api.routes_sequence import router as sequence_router
from vision_oracle.api.routes_verdicts import router as verdicts_router
from vision_oracle.api.routes_v2 import router as v2_router

api_router = APIRouter()

api_router.include_router(status_router)
api_router.include_router(evaluate_router)
api_router.include_router(trigger_router)
api_router.include_router(sequence_router)
api_router.include_router(verdicts_router)
api_router.include_router(v2_router)

