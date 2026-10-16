"""
Dataset Deduplication & Perceptual Sanitization Suite (Pillar 2).
Implements exact cryptographic hashing (SHA-256) and perceptual gradient difference hashing (dHash).
Detects exact byte duplicates and near-duplicate screens via Hamming distance thresholding.
"""

import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from PIL import Image


def compute_sha256(filepath: Union[str, Path]) -> str:
    """Computes exact cryptographic SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_dhash(image_input: Union[str, Path, Image.Image], hash_size: int = 8) -> str:
    """
    Computes perceptual difference hash (dHash) for an image.
    1. Grayscale conversion.
    2. Resizes to (hash_size + 1, hash_size) -> e.g. (9, 8) = 72 pixels.
    3. Compares adjacent horizontal pixels (P[x] > P[x+1]).
    4. Produces hash_size * hash_size (64-bit) binary fingerprint.
    """
    if isinstance(image_input, (str, Path)):
        img = Image.open(image_input)
    else:
        img = image_input

    # Convert to grayscale and resize without antialiasing smoothing
    gray = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.NEAREST)
    if hasattr(gray, "get_flattened_data"):
        pixels = list(gray.get_flattened_data())
    else:
        pixels = list(gray.getdata())

    # Build binary difference sequence
    diff_bits = []
    width = hash_size + 1
    for row in range(hash_size):
        row_offset = row * width
        for col in range(hash_size):
            left_pixel = pixels[row_offset + col]
            right_pixel = pixels[row_offset + col + 1]
            diff_bits.append("1" if left_pixel > right_pixel else "0")

    bit_string = "".join(diff_bits)
    # Convert 64-bit binary to hex string (16 characters)
    hex_str = f"{int(bit_string, 2):0{hash_size * hash_size // 4}x}"
    return hex_str


def hamming_distance(hash1_hex: str, hash2_hex: str) -> int:
    """
    Calculates number of differing bits between two equal-length hex hashes.
    Hamming distance <= 3 indicates near-identical visual layouts.
    """
    int1 = int(hash1_hex, 16)
    int2 = int(hash2_hex, 16)
    xor_result = int1 ^ int2
    return bin(xor_result).count("1")


@dataclass
class DuplicatePair:
    """Record of two files detected as exact or near-duplicates."""
    primary_file: str
    duplicate_file: str
    duplicate_type: str  # 'exact_sha256' or 'perceptual_near_duplicate'
    hamming_distance: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeduplicationReport:
    """Full empirical audit summary of dataset deduplication pass."""
    dataset_name: str
    total_files_scanned: int
    unique_files_retained: int
    exact_duplicates_found: int
    perceptual_duplicates_found: int
    hamming_threshold: int
    duplicate_pairs: List[DuplicatePair] = field(default_factory=list)

    @property
    def total_duplicates(self) -> int:
        return self.exact_duplicates_found + self.perceptual_duplicates_found

    @property
    def duplicate_rate_pct(self) -> float:
        if self.total_files_scanned == 0:
            return 0.0
        return round((self.total_duplicates / self.total_files_scanned) * 100.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "total_files_scanned": self.total_files_scanned,
            "unique_files_retained": self.unique_files_retained,
            "exact_duplicates_found": self.exact_duplicates_found,
            "perceptual_duplicates_found": self.perceptual_duplicates_found,
            "total_duplicates": self.total_duplicates,
            "duplicate_rate_pct": self.duplicate_rate_pct,
            "hamming_threshold": self.hamming_threshold,
            "duplicate_pairs": [p.to_dict() for p in self.duplicate_pairs],
        }

    def to_ascii_table(self) -> str:
        lines = [
            f"\n=== DATASET SANITIZATION & DEDUPLICATION REPORT: {self.dataset_name} ===",
            f"Total Files Scanned         : {self.total_files_scanned}",
            f"Unique Files Retained       : {self.unique_files_retained}",
            f"Exact SHA-256 Duplicates    : {self.exact_duplicates_found}",
            f"Perceptual (pHash/dHash)    : {self.perceptual_duplicates_found} (Threshold <= {self.hamming_threshold} bits)",
            f"Total Redundant Screens     : {self.total_duplicates} ({self.duplicate_rate_pct}%)",
            "-" * 65,
        ]
        if self.duplicate_pairs:
            lines.append("Sample Detected Duplicates:")
            for p in self.duplicate_pairs[:5]:
                lines.append(f"  * [{p.duplicate_type}] {Path(p.primary_file).name} <--> {Path(p.duplicate_file).name} (dist={p.hamming_distance})")
            if len(self.duplicate_pairs) > 5:
                lines.append(f"  ... and {len(self.duplicate_pairs) - 5} more.")
        else:
            lines.append("Result: 100% Unique - Zero duplicates detected.")
        return "\n".join(lines)


class DatasetDeduplicator:
    """Orchestrates exact and perceptual deduplication across physical dataset files or manifests."""

    def __init__(self, hamming_threshold: int = 3, hash_size: int = 8):
        self.hamming_threshold = hamming_threshold
        self.hash_size = hash_size

    def scan_file_list(
        self,
        file_paths: List[Union[str, Path]],
        dataset_name: str = "Dataset",
    ) -> Tuple[DeduplicationReport, List[Path]]:
        """
        Scans an ordered list of image files.
        Returns DeduplicationReport and list of unique, non-duplicate Paths.
        """
        exact_hashes: Dict[str, Path] = {}       # sha256 -> original path
        perceptual_hashes: List[Tuple[str, Path]] = [] # list of (dhash, path)

        duplicate_pairs: List[DuplicatePair] = []
        unique_paths: List[Path] = []
        exact_count = 0
        perceptual_count = 0

        for file_item in file_paths:
            p = Path(file_item)
            if not p.exists() or not p.is_file():
                continue

            # 1. Exact SHA-256 check
            sha = compute_sha256(p)
            if sha in exact_hashes:
                exact_count += 1
                duplicate_pairs.append(
                    DuplicatePair(
                        primary_file=str(exact_hashes[sha]),
                        duplicate_file=str(p),
                        duplicate_type="exact_sha256",
                        hamming_distance=0,
                    )
                )
                continue

            # 2. Perceptual dHash check
            try:
                dh = compute_dhash(p, hash_size=self.hash_size)
            except Exception:
                # If image decoding fails, skip perceptual hashing
                continue

            is_perceptual_dup = False
            for prev_dh, prev_path in perceptual_hashes:
                dist = hamming_distance(dh, prev_dh)
                if dist <= self.hamming_threshold:
                    perceptual_count += 1
                    duplicate_pairs.append(
                        DuplicatePair(
                            primary_file=str(prev_path),
                            duplicate_file=str(p),
                            duplicate_type="perceptual_near_duplicate",
                            hamming_distance=dist,
                        )
                    )
                    is_perceptual_dup = True
                    break

            if not is_perceptual_dup:
                exact_hashes[sha] = p
                perceptual_hashes.append((dh, p))
                unique_paths.append(p)

        report = DeduplicationReport(
            dataset_name=dataset_name,
            total_files_scanned=len(file_paths),
            unique_files_retained=len(unique_paths),
            exact_duplicates_found=exact_count,
            perceptual_duplicates_found=perceptual_count,
            hamming_threshold=self.hamming_threshold,
            duplicate_pairs=duplicate_pairs,
        )

        return report, unique_paths

    def scan_directory(
        self,
        directory: Union[str, Path],
        extensions: Tuple[str, ...] = (".jpg", ".jpeg", ".png"),
        dataset_name: Optional[str] = None,
    ) -> Tuple[DeduplicationReport, List[Path]]:
        """Recursively scans directory for image extensions and deduplicates."""
        dir_path = Path(directory)
        name = dataset_name or dir_path.name
        files = sorted([f for f in dir_path.rglob("*") if f.suffix.lower() in extensions])
        return self.scan_file_list(files, dataset_name=name)

    def scan_manifest_json(
        self,
        manifest_path: Union[str, Path],
        image_key: str = "image_path",
    ) -> Tuple[DeduplicationReport, List[Dict[str, Any]]]:
        """Loads a split manifest JSON, deduplicates records, and returns sanitized records."""
        path = Path(manifest_path)
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)

        file_paths = []
        for r in records:
            if isinstance(r, dict) and image_key in r:
                file_paths.append(Path(r[image_key]))
            elif isinstance(r, str):
                file_paths.append(Path(r))

        report, unique_paths = self.scan_file_list(file_paths, dataset_name=path.stem)
        unique_set = {str(p.resolve()) for p in unique_paths}

        sanitized_records = []
        for r in records:
            img_path = Path(r[image_key] if isinstance(r, dict) else r).resolve()
            if str(img_path) in unique_set:
                sanitized_records.append(r)

        return report, sanitized_records
