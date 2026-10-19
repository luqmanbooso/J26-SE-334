"""
Base Model Download Script for Component 3 (Vision Oracle).
Downloads Qwen/Qwen2-VL-2B-Instruct from Hugging Face into models/Qwen2-VL-2B-Instruct.
Usage:
    python scripts/download_base_model.py
"""

import sys
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET_DIR = REPO_ROOT / "models" / "Qwen2-VL-2B-Instruct"
DEFAULT_MODEL_ID = "Qwen/Qwen2-VL-2B-Instruct"


def check_existing_model(target_dir: Path) -> bool:
    """Checks if the target directory already contains a valid model."""
    if not target_dir.exists():
        return False
    required_files = ["config.json"]
    has_config = (target_dir / "config.json").exists()
    has_weights = any(target_dir.glob("*.safetensors")) or any(target_dir.glob("*.bin"))
    return has_config and has_weights


def download_model(model_id: str, target_dir: Path, force: bool = False) -> None:
    print(f"============================================================")
    print(f" Component 3 Base Model Downloader")
    print(f" Model ID : {model_id}")
    print(f" Target   : {target_dir}")
    print(f"============================================================")

    if not force and check_existing_model(target_dir):
        print(f"[OK] Base model already exists at: {target_dir}")
        print("[OK] Skipping download. Use --force to re-download.")
        return

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[ERROR] 'huggingface_hub' is not installed.")
        print("Please run: pip install huggingface_hub")
        print("\nOr download manually using huggingface-cli:")
        print(f"    huggingface-cli download {model_id} --local-dir {target_dir}")
        sys.exit(1)

    print(f"[INFO] Starting download from Hugging Face ({model_id})...")
    print("[INFO] This may take several minutes depending on network bandwidth (~4.4 GB)...")

    try:
        snapshot_download(
            repo_id=model_id,
            local_dir=str(target_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        print(f"\n[SUCCESS] Base model successfully downloaded to: {target_dir}")
        print("You can now run the server with:")
        print("    python -m vision_oracle.server")
    except Exception as exc:
        print(f"\n[ERROR] Download failed: {exc}")
        print("You can retry or run:")
        print(f"    huggingface-cli download {model_id} --local-dir {target_dir}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Download Qwen2-VL-2B base model for Component 3.")
    parser.add_argument(
        "--model-id",
        type=str,
        default=DEFAULT_MODEL_ID,
        help=f"Hugging Face repository ID (default: {DEFAULT_MODEL_ID})",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=DEFAULT_TARGET_DIR,
        help=f"Target directory for model weights (default: {DEFAULT_TARGET_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if model already exists.",
    )
    args = parser.parse_args()

    download_model(args.model_id, args.target_dir, args.force)


if __name__ == "__main__":
    main()
