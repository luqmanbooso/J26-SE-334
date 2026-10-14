import os
import sys

# Guarantee 'env testing' directory is present in sys.path when pytest runs directly in tests dir
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_TESTING_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(ENV_TESTING_DIR, ".."))

if ENV_TESTING_DIR not in sys.path:
    sys.path.insert(0, ENV_TESTING_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
