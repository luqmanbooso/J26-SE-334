"""Collection guards for C3's test suite.

evaluate_test_split imports torch, which is a multi-gigabyte optional
dependency this repo does not require for the other 400+ tests. Skip that
module's collection when torch is absent rather than failing the whole
repo's test run; CI or a machine with the ML stack installed still runs it.
"""
import importlib.util

collect_ignore = []
if importlib.util.find_spec("torch") is None:
    collect_ignore.append("test_evaluate_test_split.py")
