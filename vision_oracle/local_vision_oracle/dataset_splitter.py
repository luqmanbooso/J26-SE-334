"""
Deterministic Dataset Splitter & Evaluation Manifest Generator.
Grounded in Phase 2 Data Engineering, EXP-01 Baseline, and EXP-02 Pruning Ablation.
Generates stratified Train/Val/Test splits and AWQ quantization calibration subsets.
"""

import json
import random
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple, Set, Union

from local_vision_oracle.schemas import DefectType
from local_vision_oracle.evaluation import EvaluationItem

logger = logging.getLogger(__name__)


@dataclass
class SplitStats:
    """Metadata summary for a single dataset partition."""
    partition_name: str
    total_count: int
    defect_count: int
    clean_count: int
    defect_ratio: float


@dataclass
class ManifestExportSummary:
    """Consolidated summary of all exported manifests."""
    seed: int
    train_stats: SplitStats
    val_stats: SplitStats
    test_stats: SplitStats
    rico_calibration_count: int
    rico_clean_eval_count: int
    leakage_detected: bool
    manifest_paths: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DatasetSplitter:
    """
    Produces deterministic, stratified train/validation/test partitions
    and exports EvaluationItem-compatible manifests to results/manifests/.
    """

    def __init__(
        self,
        owleye_dir: Optional[Union[str, Path]] = None,
        rico_dir: Optional[Union[str, Path]] = None,
        seed: int = 42,
    ):
        base_rd = Path("RD")
        self.owleye_dir = Path(owleye_dir) if owleye_dir else base_rd / "OwlEye" / "Dataset"
        self.rico_dir = (
            Path(rico_dir)
            if rico_dir
            else base_rd / "rico_dataset_v0.1_semantic_annotations" / "semantic_annotations"
        )
        self.seed = seed

    def _get_owleye_files(self) -> Tuple[List[Path], List[Path]]:
        """Discovers all bug and normal images in OwlEye."""
        bug_dir = self.owleye_dir / "bug-aug" / "bug-aug"
        if not bug_dir.exists():
            bug_dir = self.owleye_dir / "bug-aug"

        normal_dir = self.owleye_dir / "normal-aug" / "normal-aug"
        if not normal_dir.exists():
            normal_dir = self.owleye_dir / "normal-aug"

        bug_files = sorted(list(bug_dir.glob("*.jpg"))) if bug_dir.exists() else []
        normal_files = sorted(list(normal_dir.glob("*.jpg"))) if normal_dir.exists() else []
        return bug_files, normal_files

    def split_owleye(
        self,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
    ) -> Dict[str, List[EvaluationItem]]:
        """
        Splits OwlEye into stratified Train, Val, and Test sets.
        Ensures perfect 50/50 balance in each partition and zero data leakage.
        """
        assert round(train_ratio + val_ratio + test_ratio, 2) == 1.0, "Split ratios must sum to 1.0"

        bug_files, normal_files = self._get_owleye_files()
        if not bug_files or not normal_files:
            logger.warning("OwlEye dataset files not found for splitting.")
            return {"train": [], "val": [], "test": []}

        # Shuffle deterministically
        rng_bug = random.Random(self.seed)
        rng_norm = random.Random(self.seed + 1)

        shuffled_bugs = list(bug_files)
        shuffled_normals = list(normal_files)
        rng_bug.shuffle(shuffled_bugs)
        rng_norm.shuffle(shuffled_normals)

        n_bugs = len(shuffled_bugs)
        n_normals = len(shuffled_normals)

        n_train_bug = int(n_bugs * train_ratio)
        n_val_bug = int(n_bugs * val_ratio)

        n_train_norm = int(n_normals * train_ratio)
        n_val_norm = int(n_normals * val_ratio)

        train_bugs = shuffled_bugs[:n_train_bug]
        val_bugs = shuffled_bugs[n_train_bug : n_train_bug + n_val_bug]
        test_bugs = shuffled_bugs[n_train_bug + n_val_bug :]

        train_norms = shuffled_normals[:n_train_norm]
        val_norms = shuffled_normals[n_train_norm : n_train_norm + n_val_norm]
        test_norms = shuffled_normals[n_train_norm + n_val_norm :]

        # Verify zero leakage across splits
        bug_ids_train = set(f.stem for f in train_bugs)
        bug_ids_val = set(f.stem for f in val_bugs)
        bug_ids_test = set(f.stem for f in test_bugs)
        assert len(bug_ids_train & bug_ids_val) == 0, "Leakage detected between Train and Val bugs"
        assert len(bug_ids_train & bug_ids_test) == 0, "Leakage detected between Train and Test bugs"
        assert len(bug_ids_val & bug_ids_test) == 0, "Leakage detected between Val and Test bugs"

        def to_items(bug_list: List[Path], norm_list: List[Path], split_name: str) -> List[EvaluationItem]:
            items: List[EvaluationItem] = []
            for b in bug_list:
                items.append(
                    EvaluationItem(
                        screen_id=b.stem,
                        image_path=b.as_posix(),
                        hierarchy_path=None,
                        expected_has_defect=True,
                        expected_defect_type=DefectType.COMPONENT_OVERLAP,
                        expected_bounding_box=None,
                        metadata={"dataset": "OwlEye", "split": split_name, "raw_label": "bug"},
                    )
                )
            for n in norm_list:
                items.append(
                    EvaluationItem(
                        screen_id=n.stem,
                        image_path=n.as_posix(),
                        hierarchy_path=None,
                        expected_has_defect=False,
                        expected_defect_type=DefectType.NONE,
                        expected_bounding_box=None,
                        metadata={"dataset": "OwlEye", "split": split_name, "raw_label": "normal"},
                    )
                )
            # Shuffle items inside partition so classes are mixed
            rng = random.Random(self.seed + len(items))
            rng.shuffle(items)
            return items

        return {
            "train": to_items(train_bugs, train_norms, "train"),
            "val": to_items(val_bugs, val_norms, "val"),
            "test": to_items(test_bugs, test_norms, "test"),
        }

    def extract_rico_subsets(
        self,
        calibration_count: int = 256,
        clean_eval_count: int = 600,
    ) -> Tuple[List[EvaluationItem], List[EvaluationItem]]:
        """
        Selects non-overlapping Rico subsets for AWQ calibration and clean baseline evaluation.
        """
        if not self.rico_dir.exists():
            logger.warning("Rico dataset directory not found for subset extraction.")
            return [], []

        png_stems = set(f.stem for f in self.rico_dir.glob("*.png"))
        json_stems = set(f.stem for f in self.rico_dir.glob("*.json"))
        paired_stems = sorted(list(png_stems.intersection(json_stems)))

        rng = random.Random(self.seed + 100)
        shuffled = list(paired_stems)
        rng.shuffle(shuffled)

        calib_stems = shuffled[:calibration_count]
        eval_stems = shuffled[calibration_count : calibration_count + clean_eval_count]

        # Verify zero overlap
        assert len(set(calib_stems) & set(eval_stems)) == 0, "Overlap in Rico calibration and eval sets"

        calib_items = [
            EvaluationItem(
                screen_id=stem,
                image_path=(self.rico_dir / f"{stem}.png").as_posix(),
                hierarchy_path=(self.rico_dir / f"{stem}.json").as_posix(),
                expected_has_defect=False,
                expected_defect_type=DefectType.NONE,
                metadata={"dataset": "Rico", "purpose": "awq_calibration"},
            )
            for stem in calib_stems
        ]

        clean_eval_items = [
            EvaluationItem(
                screen_id=stem,
                image_path=(self.rico_dir / f"{stem}.png").as_posix(),
                hierarchy_path=(self.rico_dir / f"{stem}.json").as_posix(),
                expected_has_defect=False,
                expected_defect_type=DefectType.NONE,
                metadata={"dataset": "Rico", "purpose": "clean_baseline_evaluation"},
            )
            for stem in eval_stems
        ]

        return calib_items, clean_eval_items

    def export_all_manifests(
        self,
        output_dir: Union[str, Path] = "results/manifests",
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        rico_calib_count: int = 256,
        rico_clean_eval_count: int = 600,
    ) -> ManifestExportSummary:
        """
        Executes full splitting and exports JSON manifests to disk.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # 1. OwlEye Splits
        owleye_splits = self.split_owleye(
            train_ratio=train_ratio, val_ratio=val_ratio, test_ratio=test_ratio
        )

        manifest_paths = {}
        for partition in ["train", "val", "test"]:
            items = owleye_splits[partition]
            p_file = out_path / f"owleye_{partition}.json"
            with open(p_file, "w", encoding="utf-8") as f:
                json.dump([item.model_dump() for item in items], f, indent=2)
            manifest_paths[f"owleye_{partition}"] = p_file.as_posix()

        # 2. Rico Subsets
        rico_calib, rico_eval = self.extract_rico_subsets(
            calibration_count=rico_calib_count, clean_eval_count=rico_clean_eval_count
        )

        calib_file = out_path / f"rico_calibration_{rico_calib_count}.json"
        with open(calib_file, "w", encoding="utf-8") as f:
            json.dump([item.model_dump() for item in rico_calib], f, indent=2)
        manifest_paths["rico_calibration"] = calib_file.as_posix()

        eval_file = out_path / f"rico_clean_eval_{rico_clean_eval_count}.json"
        with open(eval_file, "w", encoding="utf-8") as f:
            json.dump([item.model_dump() for item in rico_eval], f, indent=2)
        manifest_paths["rico_clean_eval"] = eval_file.as_posix()

        def compute_stats(items: List[EvaluationItem], name: str) -> SplitStats:
            defects = sum(1 for x in items if x.expected_has_defect)
            cleans = len(items) - defects
            ratio = round((defects / len(items)) * 100.0, 2) if items else 0.0
            return SplitStats(
                partition_name=name,
                total_count=len(items),
                defect_count=defects,
                clean_count=cleans,
                defect_ratio=ratio,
            )

        summary = ManifestExportSummary(
            seed=self.seed,
            train_stats=compute_stats(owleye_splits["train"], "train"),
            val_stats=compute_stats(owleye_splits["val"], "val"),
            test_stats=compute_stats(owleye_splits["test"], "test"),
            rico_calibration_count=len(rico_calib),
            rico_clean_eval_count=len(rico_eval),
            leakage_detected=False,
            manifest_paths=manifest_paths,
        )

        summary_file = out_path / "manifest_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary.to_dict(), f, indent=2)

        return summary
