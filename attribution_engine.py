import os
import sys
from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    class EnvironmentAttributionEngine:
        perturbation_log_path: str
        def __init__(self, perturbation_log_path: str = "perturbation_event_log.json", *args: Any, **kwargs: Any) -> None: ...
        def correlate(
            self,
            failures: List[Dict[str, Any]],
            perturbation_events: Optional[List[Dict[str, Any]]] = None,
            time_window_sec: float = 3.5
        ) -> Dict[str, Any]: ...
        def _load_events(self) -> List[Dict[str, Any]]: ...
        def export_report(self, report: Dict[str, Any], output_path: str = "environment_failure_attribution.json") -> None: ...
else:
    import importlib.util
    _file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "env testing", "attribution_engine.py")
    _spec = importlib.util.spec_from_file_location("_real_attribution_engine", _file_path)
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        EnvironmentAttributionEngine = getattr(_mod, "EnvironmentAttributionEngine")
        if hasattr(_mod, "main"):
            main = getattr(_mod, "main")

__all__ = ["EnvironmentAttributionEngine"]
