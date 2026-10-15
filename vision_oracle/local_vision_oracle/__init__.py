"""
Local Vision Oracle (Component 3 of HEART Framework)
Localized Multimodal Vision-Semantic Test Oracle for Android Mobile Applications.
"""

__version__ = "0.1.0"
__author__ = "M.L. Booso"

from local_vision_oracle.schemas import (
    DefectType,
    Verdict,
    LatencyBreakdown,
    C3OracleResult,
)
from local_vision_oracle.pruner import (
    HierarchyPruner,
    PrunedNode,
)
from local_vision_oracle.preprocessor import (
    ImagePreprocessor,
    PreprocessedImage,
)
from local_vision_oracle.prompt import (
    PromptBuilder,
    VerdictParser,
    ORACLE_SYSTEM_PROMPT,
)
from local_vision_oracle.engine import (
    InferenceBackend,
    MockInferenceBackend,
    TransformersInferenceBackend,
    OracleEngine,
)
from local_vision_oracle.evaluation import (
    EvaluationItem,
    EvaluationMetrics,
    Evaluator,
    compute_bbox_iou,
    mcnemar_test,
)
from local_vision_oracle.dataset_scanner import (
    DatasetScanner,
    OwlEyeAuditResult,
    RicoAuditResult,
    CompleteAuditReport,
)
from local_vision_oracle.dataset_splitter import (
    DatasetSplitter,
    SplitStats,
    ManifestExportSummary,
)
from local_vision_oracle.calibration import (
    AWQConfig,
    MemoryProfile,
    AWQCalibrationSummary,
    AWQCalibrator,
)
from local_vision_oracle.confusion_matrix import (
    BinaryConfusionMatrix,
    ConfusionMatrixCalculator,
)

__all__ = [
    "DatasetScanner",
    "OwlEyeAuditResult",
    "RicoAuditResult",
    "CompleteAuditReport",
    "DatasetSplitter",
    "SplitStats",
    "ManifestExportSummary",
    "AWQConfig",
    "MemoryProfile",
    "AWQCalibrationSummary",
    "AWQCalibrator",
    "BinaryConfusionMatrix",
    "ConfusionMatrixCalculator",
    "DefectType",
    "Verdict",
    "LatencyBreakdown",
    "C3OracleResult",
    "HierarchyPruner",
    "PrunedNode",
    "ImagePreprocessor",
    "PreprocessedImage",
    "PromptBuilder",
    "VerdictParser",
    "ORACLE_SYSTEM_PROMPT",
    "InferenceBackend",
    "MockInferenceBackend",
    "TransformersInferenceBackend",
    "OracleEngine",
    "EvaluationItem",
    "EvaluationMetrics",
    "Evaluator",
    "compute_bbox_iou",
    "mcnemar_test",
]


