"""
Automated Dataset Scanner & Integrity Auditor for OwlEye and Rico Datasets.
Grounded in Phase 2 Data Engineering, EXP-01 Baseline, and EXP-02 Pruning Ablation.
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple, Union
from PIL import Image

from local_vision_oracle.pruner import HierarchyPruner

logger = logging.getLogger(__name__)


@dataclass
class OwlEyeAuditResult:
    """Audit results for the OwlEye UI defect dataset."""
    dataset_name: str = "OwlEye UI Defect Dataset"
    location: str = ""
    bug_image_count: int = 0
    normal_image_count: int = 0
    total_images: int = 0
    is_balanced: bool = False
    sample_resolutions: List[Tuple[int, int]] = field(default_factory=list)
    sample_modes: List[str] = field(default_factory=list)
    corrupt_files_detected: int = 0
    verified: bool = False


@dataclass
class RicoAuditResult:
    """Audit results for the Rico mobile semantic annotations dataset."""
    dataset_name: str = "Rico Mobile Dataset"
    location: str = ""
    total_png_count: int = 0
    total_json_count: int = 0
    paired_count: int = 0
    orphaned_png_count: int = 0
    orphaned_json_count: int = 0
    sample_resolutions: List[Tuple[int, int]] = field(default_factory=list)
    sample_modes: List[str] = field(default_factory=list)
    sample_pruning_ratio: float = 0.0
    verified: bool = False


@dataclass
class CompleteAuditReport:
    """Consolidated audit report across all evaluation datasets."""
    timestamp: str
    owleye: OwlEyeAuditResult
    rico: RicoAuditResult
    summary_verdict: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DatasetScanner:
    """
    Scans, verifies, and extracts empirical statistics from physical datasets.
    """

    def __init__(
        self,
        owleye_dir: Optional[Union[str, Path]] = None,
        rico_dir: Optional[Union[str, Path]] = None,
    ):
        base_rd = Path("RD")
        self.owleye_dir = Path(owleye_dir) if owleye_dir else base_rd / "OwlEye" / "Dataset"
        self.rico_dir = Path(rico_dir) if rico_dir else base_rd / "rico_dataset_v0.1_semantic_annotations" / "semantic_annotations"

    def audit_owleye(self, sample_limit: int = 10) -> OwlEyeAuditResult:
        """
        Audits OwlEye directory for bug and clean screenshot counts and format sanity.
        """
        result = OwlEyeAuditResult(location=str(self.owleye_dir))
        if not self.owleye_dir.exists():
            logger.warning(f"OwlEye directory not found at {self.owleye_dir}")
            return result

        bug_dir = self.owleye_dir / "bug-aug" / "bug-aug"
        if not bug_dir.exists():
            # Fallback to direct bug-aug folder
            bug_dir = self.owleye_dir / "bug-aug"

        normal_dir = self.owleye_dir / "normal-aug" / "normal-aug"
        if not normal_dir.exists():
            # Fallback to direct normal-aug folder
            normal_dir = self.owleye_dir / "normal-aug"

        bug_files = list(bug_dir.glob("*.jpg")) if bug_dir.exists() else []
        normal_files = list(normal_dir.glob("*.jpg")) if normal_dir.exists() else []

        result.bug_image_count = len(bug_files)
        result.normal_image_count = len(normal_files)
        result.total_images = result.bug_image_count + result.normal_image_count
        result.is_balanced = (
            result.bug_image_count == result.normal_image_count and result.total_images > 0
        )

        # Sample check image resolutions and integrity
        sample_files = bug_files[:sample_limit] + normal_files[:sample_limit]
        resolutions = []
        modes = []
        corrupt = 0

        for f in sample_files:
            try:
                with Image.open(f) as img:
                    img.verify()
                with Image.open(f) as img:
                    resolutions.append(img.size)
                    modes.append(img.mode)
            except Exception as e:
                logger.error(f"Corrupt image {f}: {e}")
                corrupt += 1

        result.sample_resolutions = list(set(resolutions))
        result.sample_modes = list(set(modes))
        result.corrupt_files_detected = corrupt
        result.verified = result.total_images > 0 and corrupt == 0
        return result

    def audit_rico(self, sample_limit: int = 10) -> RicoAuditResult:
        """
        Audits Rico directory for paired PNG and JSON hierarchies and pruning ratios.
        """
        result = RicoAuditResult(location=str(self.rico_dir))
        if not self.rico_dir.exists():
            logger.warning(f"Rico directory not found at {self.rico_dir}")
            return result

        png_stems = set(f.stem for f in self.rico_dir.glob("*.png"))
        json_stems = set(f.stem for f in self.rico_dir.glob("*.json"))

        result.total_png_count = len(png_stems)
        result.total_json_count = len(json_stems)
        paired = png_stems.intersection(json_stems)
        result.paired_count = len(paired)
        result.orphaned_png_count = len(png_stems - json_stems)
        result.orphaned_json_count = len(json_stems - png_stems)

        # Sample check image resolutions and modes
        sample_paired = list(paired)[:sample_limit]
        resolutions = []
        modes = []
        raw_nodes_total = 0
        pruned_nodes_total = 0

        pruner = HierarchyPruner(screen_width=1440, screen_height=2560, max_nodes=50)

        for stem in sample_paired:
            png_path = self.rico_dir / f"{stem}.png"
            json_path = self.rico_dir / f"{stem}.json"

            try:
                with Image.open(png_path) as img:
                    resolutions.append(img.size)
                    modes.append(img.mode)
            except Exception as e:
                logger.error(f"Error reading Rico PNG {png_path}: {e}")

            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                nodes = pruner.prune_rico_json(data)
                raw_nodes_total += pruner.raw_node_count
                pruned_nodes_total += len(nodes)
            except Exception as e:
                logger.error(f"Error parsing Rico JSON {json_path}: {e}")

        result.sample_resolutions = list(set(resolutions))
        result.sample_modes = list(set(modes))

        if raw_nodes_total > 0:
            result.sample_pruning_ratio = round(
                (1.0 - (pruned_nodes_total / raw_nodes_total)) * 100.0, 2
            )

        result.verified = (
            result.paired_count > 0 and result.orphaned_png_count == 0 and result.orphaned_json_count == 0
        )
        return result

    def generate_full_report(self, output_path: Optional[Union[str, Path]] = None) -> CompleteAuditReport:
        """
        Runs complete audit across both datasets and outputs JSON report.
        """
        import datetime
        owleye_result = self.audit_owleye()
        rico_result = self.audit_rico()

        verdict = "PASSED" if (owleye_result.verified and rico_result.verified) else "FAILED"

        report = CompleteAuditReport(
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            owleye=owleye_result,
            rico=rico_result,
            summary_verdict=verdict,
        )

        if output_path:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, indent=2)
            logger.info(f"Audit report saved to {out_file}")

        return report
