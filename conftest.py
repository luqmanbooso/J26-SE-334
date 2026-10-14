import os
import sys

# Guarantee 'env testing' and root are always present on sys.path across all platforms
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_TESTING_DIR = os.path.join(ROOT_DIR, "env testing")

if ENV_TESTING_DIR not in sys.path:
    sys.path.insert(0, ENV_TESTING_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
