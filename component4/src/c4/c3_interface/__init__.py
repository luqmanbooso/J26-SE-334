"""Component 3 contract and client implementations."""

from c4.c3_interface.client import C3Client
from c4.c3_interface.contract import C3Verdict, DefectRegion, ScreenshotEvidence
from c4.c3_interface.live_client import C3LiveClient
from c4.c3_interface.mock_client import MockC3Client
from c4.c3_interface.normalize import normalize_defect_type, normalize_verdict

__all__ = [
    "C3Client",
    "C3LiveClient",
    "C3Verdict",
    "DefectRegion",
    "MockC3Client",
    "ScreenshotEvidence",
    "normalize_defect_type",
    "normalize_verdict",
]
