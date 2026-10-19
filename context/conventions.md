---
type: singleton
domain: conventions
updated: 2026-10-17
---
# Conventions & Tech Stack

## Tech Stack
- **Languages:** Python 3.10+ (tested on Python 3.13)
- **API Framework:** FastAPI, Uvicorn, Pydantic v2
- **Deep Learning / VLM:** PyTorch, HuggingFace Transformers, AutoAWQ (Qwen2-VL 7B / 2B quantized)
- **Testing & Verification:** Pytest, pytest-asyncio, Appium Python Client
- **Device Control:** Android Debug Bridge (ADB), UIAutomator 2 XML dumps
- **Desktop UI:** PyQt5 / Tkinter / HTML5 local studio

## Architectural Invariants
- **Zero Cloud Egress:** All inference (C3), perturbation (C1), stress simulation (C2), and healing (C4) must run offline locally.
- **Unified Device Bridge:** Direct ADB interactions route through `common.adb.AdbDevice`.
- **Modular Repositories:** Each component (C1, C2, C3, C4) operates independently with clear contract interfaces (`IF-C2-to-C3`, `IF-C3-to-C4`).
