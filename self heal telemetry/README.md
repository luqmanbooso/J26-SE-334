# Component 4: Telemetry-Driven Self-Healing Test Synthesis Engine

**Student:** H.N. Madubashini (IT23192300)  
**Research Project:** J26-SE-334 — Human Behavior-Aware Robustness Testing Framework for Mobile Applications

---

## Overview

Production crash reproduction is typically stalled by incomplete human bug reports, and regression test suites frequently break when UI locators change across app versions (selector brittleness).

The **Telemetry-Driven Self-Healing Test Synthesis Engine** addresses these challenges by transforming raw production telemetry breadcrumbs (e.g. Sentry, Firebase Crashlytics) directly into executable Appium regression test scripts, and automatically repairing broken locators using **Sentence-BERT semantic embedding similarity** and AST-based structure matching.

---

## Key Features & Capabilities

- **Telemetry-to-Test Compilation:** Ingests raw Sentry/Firebase breadcrumb trails and converts interaction flows into executable test scenarios.
- **Sentence-BERT Semantic Locator Healing:** Computes cosine similarity across UI element attributes (text, resource ID, accessibility label, class) to remap selectors when UI structures shift.
- **AST & DOM Structural Matching:** Preserves test intent across application updates by analyzing UI hierarchy diffs.
- **Self-Healing Test Runner:** Executes tests dynamically, intercepts locator failures at runtime, automatically replaces failed selectors with the best semantic match, and updates test scripts.

---

## Directory Structure

```text
self heal telemetry/
├── core/
│   ├── ast_analyzer.py             # AST parsing and UI hierarchy structural comparator
│   ├── breadcrumb_parser.py        # Telemetry parser for Sentry / Firebase breadcrumb sequences
│   └── test_generator.py           # Automated test generator synthesizing Appium scripts
├── healing/
│   ├── sbert_matcher.py            # Sentence-BERT semantic similarity locator matcher
│   └── self_healer.py              # Dynamic runtime locator repair engine
├── data/
│   ├── sample_telemetry.json       # Example raw production telemetry logs
│   └── broken_test_sample.py       # Sample regression script with stale selectors
├── tests/                          # Synthesized and repaired test suites
├── run_live_healing_suite.py       # Live execution suite demonstrating runtime locator healing
├── run_test_repairer.py            # Offline script remapping and test repair runner
├── window_dump.xml                 # UI hierarchy snapshot for locator resolution
└── requirements.txt                # Component dependencies
```

---

## Prerequisites & Installation

1. **Prerequisites:**
   - Python 3.10+
   - Appium server / Android ADB setup for live execution

2. **Setup:**
   ```bash
   cd "self heal telemetry"
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

---

## Usage

### 1. Compile Telemetry into Test Scripts
Transform production traces into test cases:
```bash
python core/test_generator.py
```

### 2. Repair Broken Locators Offline
Run Sentence-BERT semantic remapping on outdated test scripts:
```bash
python run_test_repairer.py
```

### 3. Run Live Self-Healing Test Suite
Execute the test suite with automatic runtime fallback and healing:
```bash
python run_live_healing_suite.py
```
