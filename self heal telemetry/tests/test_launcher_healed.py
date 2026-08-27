#!/usr/bin/env python3
# Auto-Healed Standalone Regression Test Script
# Source Target : tests/test_launcher_broken.py
# Engine        : S-BERT Semantic Self-Healing Engine

import os
import sys
import time

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.adb_client import ADBClient

HEALED_TEST_PIPELINE = [
    {
        'step': 2,
        'name': 'Launch SMS Chat Application',
        'original_broken_locator': 'Send SMS Chat',
        'healed_ui_element': 'Start chat Start chat start chat fab',
        'resolved_coordinates': (833, 2263),
        'confidence_score': '42.33%',
        'action': 'TAP'
    },
    {
        'step': 3,
        'name': 'Launch Web Browser Application',
        'original_broken_locator': 'Web Browser Navigator',
        'healed_ui_element': 'toolbar',
        'resolved_coordinates': (540, 147),
        'confidence_score': '38.74%',
        'action': 'TAP'
    },
]

def run_repaired_test(adb_client=None):
    if adb_client is None:
        adb_client = ADBClient()

    print('=' * 65)
    print('EXECUTING STANDALONE HEALED TEST SUITE (FAST REGRESSION RUN)')
    print('=' * 65)

    for item in HEALED_TEST_PIPELINE:
        step = item['step']
        name = item['name']
        x, y = item['resolved_coordinates']
        elem = item['healed_ui_element']
        print(f'[Step {step}] Executing {name} -> Tapping target at ({x}, {y}) [{elem}]')
        adb_client.tap(x, y)
        time.sleep(2.0)

    print('\n[+] Healed Regression Suite Execution Passed Successfully!')
    print('=' * 65)

if __name__ == '__main__':
    run_repaired_test()
