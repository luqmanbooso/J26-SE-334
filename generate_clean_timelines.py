"""
Forwarder for results/generate_clean_timelines.py
Ensures root-level import 'from generate_clean_timelines import plot_live_pipeline_timeline' works.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_RESULTS = os.path.join(_ROOT, "results")
if _RESULTS not in sys.path:
    sys.path.insert(0, _RESULTS)

try:
    from results.generate_clean_timelines import *  # type: ignore
except ImportError:
    try:
        from generate_clean_timelines import *  # type: ignore
    except ImportError:
        pass
