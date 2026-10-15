"""Put the component root on sys.path so tests import its modules the same way
its scripts do (`from models.spatial import ...`), mirroring the repository
root conftest."""
import os
import sys

BIOMETRY_DIR = os.path.dirname(os.path.abspath(__file__))
if BIOMETRY_DIR not in sys.path:
    sys.path.insert(0, BIOMETRY_DIR)
