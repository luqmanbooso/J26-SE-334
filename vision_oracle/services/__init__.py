"""
Component 3 Service Layer.
"""

from vision_oracle.services.oracle_service import (
    OracleService,
    get_oracle_service,
    set_oracle_service,
)
from vision_oracle.services.trigger_queue import process_c2_trigger_task

__all__ = [
    "OracleService",
    "get_oracle_service",
    "set_oracle_service",
    "process_c2_trigger_task",
]
