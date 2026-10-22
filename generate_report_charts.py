import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    def generate_findings_chart_report() -> str: ...
else:
    import importlib.util
    _file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "env testing", "generate_report_charts.py")
    _spec = importlib.util.spec_from_file_location("_real_generate_report_charts", _file_path)
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        generate_findings_chart_report = getattr(_mod, "generate_findings_chart_report")

__all__ = ["generate_findings_chart_report"]

if __name__ == "__main__":
    generate_findings_chart_report()
