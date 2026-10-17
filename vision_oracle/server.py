"""
FastAPI REST Application Entrypoint for Component 3.
Localized Multimodal Vision-Semantic Test Oracle (J26-SE-334).

Fulfills:
- Proposal FR5: Zero cloud egress (100% offline localhost REST API).
- Proposal FR6: Asynchronous C2 capture trigger queue.
- Proposal FR7: C4 verdict publishing envelope and ledger.
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure path resolution for direct execution
C3_ROOT = Path(__file__).resolve().parent
REPO_ROOT = C3_ROOT.parent
if str(C3_ROOT) not in sys.path:
    sys.path.insert(0, str(C3_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vision_oracle.core.config import SERVICE_TITLE, SERVICE_VERSION
from vision_oracle.api.router import api_router
from vision_oracle.services.oracle_service import (
    OracleService,
    get_oracle_service,
    set_oracle_service,
)
from local_vision_oracle.engine import OracleEngine


def get_engine() -> OracleEngine:
    """Helper for backwards compatibility with tests and callers."""
    return get_oracle_service().engine


def set_engine(engine: OracleEngine) -> None:
    """Helper for backwards compatibility to inject custom/mock engines."""
    set_oracle_service(OracleService(engine=engine))


def create_app() -> FastAPI:
    """Application factory for C3 Oracle service."""
    application = FastAPI(
        title=SERVICE_TITLE,
        description="Offline REST service for non-crash UI failure detection, SAHI tiling, and C4 verdict publishing.",
        version=SERVICE_VERSION,
        docs_url=None,
        redoc_url=None,
    )


    # Enable CORS for local developer dashboard / loopback access
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount master modular router
    application.include_router(api_router)

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn
    from vision_oracle.core.config import SERVICE_PORT
    uvicorn.run(app, host="127.0.0.1", port=SERVICE_PORT, log_level="info")
