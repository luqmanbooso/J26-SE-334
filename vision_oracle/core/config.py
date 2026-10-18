"""
Configuration and constants for Component 3 service layer.
Dynamically resolves local model weights, LoRA adapters, and workspace paths.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Union

C3_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = C3_DIR.parent
C4_SRC = REPO_ROOT / "component4" / "src"
if C4_SRC.exists() and str(C4_SRC) not in sys.path:
    sys.path.insert(0, str(C4_SRC))

NOTEBOOK_DIR = C3_DIR / "notebooks"
RESEARCH_ROOT = Path(os.getenv("RESEARCH_ROOT", str(REPO_ROOT.parent)))

VERDICTS_DIR = REPO_ROOT / "results" / "verdicts"
VERDICTS_DIR.mkdir(parents=True, exist_ok=True)




def resolve_path(rel_candidate: Union[str, Path]) -> Optional[Path]:
    """
    Dynamically searches multiple workspace roots to resolve relative file/model paths.
    Matches logic tested in vision_oracle/notebooks/oracle_demonstration.ipynb.
    """
    if not rel_candidate:
        return None

    cand = Path(rel_candidate)
    if cand.is_absolute() and cand.exists():
        return cand

    search_roots = [
        Path.cwd(),
        NOTEBOOK_DIR,
        C3_DIR,
        REPO_ROOT,
        REPO_ROOT / "models",
        C3_DIR / "results" / "weights",
        C3_DIR / "results",
        RESEARCH_ROOT,
        RESEARCH_ROOT / "RD" / "models",
        RESEARCH_ROOT / "results",
    ]

    for root in search_roots:
        target = (root / cand).resolve()
        if target.exists():
            return target

    # Fallback absolute join with research root
    fallback = (RESEARCH_ROOT / cand).resolve()
    if fallback.exists():
        return fallback

    return None


BASE_MODEL_PATH = resolve_path("models/Qwen2-VL-2B-Instruct") or resolve_path("RD/models/Qwen2-VL-2B-Instruct")
LORA_WEIGHTS_PATH = (
    resolve_path("models/c3_lora_final")
    or resolve_path("results/weights/c3_lora_final")
    or resolve_path("results/c3_lora_final")
)

SERVICE_PORT = int(os.getenv("C3_PORT", "8003"))
SERVICE_TITLE = "HEART Component 3 - Localized Vision-Semantic Oracle API"
SERVICE_VERSION = "1.0.0"
ZERO_CLOUD_EGRESS = True

