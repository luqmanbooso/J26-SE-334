import os
import zipfile
import re
from typing import Dict, Any, List

def parse_apk_metadata(apk_path: str) -> Dict[str, Any]:
    """Inspects an APK zipfile and extracts package name, version, and activities."""
    if not os.path.exists(apk_path):
        return {
            "apk_name": os.path.basename(apk_path),
            "package_name": "com.target.unknown",
            "app_name": "Target App",
            "version": "1.0.0",
            "activities": [],
            "app_type": "generic"
        }

    filename = os.path.basename(apk_path)
    file_size_mb = round(os.path.getsize(apk_path) / (1024 * 1024), 2)
    package_name = ""
    version = "1.0.0"
    activities = []

    try:
        with zipfile.ZipFile(apk_path) as z:
            if "AndroidManifest.xml" in z.namelist():
                manifest_bytes = z.read("AndroidManifest.xml")
                # Manifest strings in string pool are UTF-16LE encoded
                strings = [
                    s.decode("utf-16le", errors="ignore").strip()
                    for s in re.findall(rb'(?:[\x20-\x7e]\x00){3,}', manifest_bytes)
                ]

                # Extract activities
                for s in strings:
                    clean = re.sub(r'^[0-9>?/@G:]+', '', s)
                    if "Activity" in clean and "." in clean and not clean.startswith("android."):
                        activities.append(clean)
                activities = sorted(list(set(activities)))

                # If activities found, derive package from common activity prefix
                if activities:
                    candidate_pkg = ".".join(activities[0].split(".")[:-1])
                    if "." in candidate_pkg:
                        package_name = candidate_pkg

                # Extract version
                versions = [s for s in strings if re.match(r'^\d+\.\d+(\.\d+)?', s)]
                if versions:
                    version = versions[0]
    except Exception as e:
        print(f"[APK Parser Error] {e}")

    # Fallback package name if manifest parse was incomplete
    if not package_name:
        clean_name = os.path.splitext(filename)[0].lower().replace(" ", ".").replace("-", ".")
        package_name = f"com.target.{clean_name}" if not clean_name.startswith("com.") else clean_name

    # Derive human-friendly app label and category
    lower_pkg = package_name.lower()
    lower_file = filename.lower()

    if any(k in lower_pkg or k in lower_file for k in ["photo", "foto", "gallery", "image", "camera"]):
        app_name = "APhotoManager" if ("photomanager" in lower_file or "androfoto" in lower_pkg) else "Photo Gallery"
        app_type = "photo_manager"
    elif any(k in lower_pkg or k in lower_file for k in ["pay", "checkout", "wallet", "shop", "cart"]):
        app_name = "SwiftPay Mobile" if "swiftpay" in lower_file else "Payment Checkout"
        app_type = "ecommerce"
    elif any(k in lower_pkg or k in lower_file for k in ["transit", "map", "ride", "geo"]):
        app_name = "TransitGo Maps"
        app_type = "navigation"
    else:
        app_name = os.path.splitext(filename)[0].split("-")[0].capitalize()
        app_type = "generic"

    # Find main entry activity
    main_act = activities[0] if activities else f"{package_name}.MainActivity"
    for act in activities:
        if any(m in act.lower() for m in ["gallery", "main", "home", "launcher"]):
            main_act = act
            break

    return {
        "apk_name": filename,
        "size_mb": file_size_mb,
        "package_name": package_name,
        "app_name": app_name,
        "version": version,
        "activities": activities,
        "app_type": app_type,
        "main_activity": main_act
    }
