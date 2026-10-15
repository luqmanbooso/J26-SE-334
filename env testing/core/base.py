from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from core.adb_client import ADBClient
from core.event_logger import EventLogger

class BaseStressor(ABC):
    """Abstract base class for all environmental perturbation stressors."""

    def __init__(self, adb: ADBClient, logger: EventLogger, category: str):
        self.adb = adb
        self.logger = logger
        self.category = category
        self.is_active: bool = False
        self.current_state: Dict[str, Any] = {}

    @abstractmethod
    def apply(self, **kwargs) -> bool:
        """Applies specific perturbation condition."""
        pass

    @abstractmethod
    def revert(self) -> bool:
        """Reverts perturbation back to nominal baseline."""
        pass

    def get_state(self) -> Dict[str, Any]:
        """Returns the current stress state dictionary."""
        return {
            "category": self.category,
            "is_active": self.is_active,
            "state": self.current_state
        }
