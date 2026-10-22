"""
Local Vision Oracle (Component 3 of HEART Framework)
Localized Multimodal Vision-Semantic Test Oracle for Android Mobile Applications.
"""

__version__ = "0.1.0"
__author__ = "M.L. Booso"

from .schemas import (
    DefectType,
    Verdict,
    LatencyBreakdown,
    C3OracleResult,
)
from .pruner import (
    HierarchyPruner,
    PrunedNode,
)
from .preprocessor import (
    ImagePreprocessor,
    PreprocessedImage,
)
from .prompt import (
    PromptBuilder,
    VerdictParser,
    ORACLE_SYSTEM_PROMPT,
)
from .engine import (
    InferenceBackend,
    MockInferenceBackend,
    TransformersInferenceBackend,
    OracleEngine,
)
from .evaluation import (
    EvaluationItem,
    EvaluationMetrics,
    Evaluator,
    compute_bbox_iou,
    mcnemar_test,
)
from .dataset_scanner import (
    DatasetScanner,
    OwlEyeAuditResult,
    RicoAuditResult,
    CompleteAuditReport,
)
from .dataset_splitter import (
    DatasetSplitter,
    SplitStats,
    ManifestExportSummary,
)
from .calibration import (
    AWQConfig,
    MemoryProfile,
    AWQCalibrationSummary,
    AWQCalibrator,
)
from .confusion_matrix import (
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


