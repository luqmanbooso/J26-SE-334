import os
import sys

# Put every component's import root on sys.path, so `pytest` from the repository
# root collects all of them. Directories whose names contain spaces cannot be
# packages, so each one has to be added explicitly.
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

_IMPORT_ROOTS = [
    ROOT_DIR,                                   # common/, tests/
    os.path.join(ROOT_DIR, "env testing"),      # C1
    os.path.join(ROOT_DIR, "component4", "src"),  # C4's packaged component
]

for _path in _IMPORT_ROOTS:
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)
