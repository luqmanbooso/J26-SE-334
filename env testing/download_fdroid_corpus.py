"""Downloads curated F-Droid APKs into ``env testing/uploads/`` (20-30 app proposal corpus)."""

from __future__ import annotations

import concurrent.futures
import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

from core.benchmark_catalog import FDROID_CORPUS_25

EXTRA_FDROID_CANDIDATES: List[str] = [
    "com.simplemobiletools.notes.pro",
    "com.simplemobiletools.calendar.pro",
    "com.simplemobiletools.calculator",
    "com.simplemobiletools.filemanager.pro",
    "org.secuso.privacyfriendlytodolist",
    "org.secuso.privacyfriendlynotes",
    "com.kunzisoft.keepass.free",
    "de.baumann.browser",
    "com.fsck.k9",
    "com.amaze.filemanager",
    "org.fossify.gallery",
    "org.fossify.notes",
    "org.fossify.clock",
    "org.fossify.calculator",
    "app.fedilab.fedilab",
    "org.isoron.uhabits",
]

MAX_APK_BYTES = 25 * 1024 * 1024  # keep downloads fast and responsive


def fetch_apk(pkg: str, uploads_dir: str) -> Optional[str]:
    """Queries F-Droid package API and downloads suggested APK if <= MAX_APK_BYTES."""
    api_url = f"https://f-droid.org/api/v1/packages/{pkg}"
    req = urllib.request.Request(api_url, headers={"User-Agent": "HEART-C1-Corpus/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        vc = meta.get("suggestedVersionCode") or (meta.get("packages") or [{}])[0].get("versionCode")
        if not vc:
            return None
        apk_name = f"{pkg}_{vc}.apk"
        dest = os.path.join(uploads_dir, apk_name)
        if os.path.exists(dest) and os.path.getsize(dest) > 10000:
            return dest

        apk_url = f"https://f-droid.org/repo/{apk_name}"
        head_req = urllib.request.Request(apk_url, method="HEAD", headers={"User-Agent": "HEART-C1-Corpus/1.0"})
        with urllib.request.urlopen(head_req, timeout=10) as hresp:
            clen = int(hresp.headers.get("Content-Length") or 0)
            if clen > MAX_APK_BYTES:
                print(f"[-] Skip {pkg} ({round(clen / (1024 * 1024), 1)} MB > 25 MB limit)")
                return None

        dl_req = urllib.request.Request(apk_url, headers={"User-Agent": "HEART-C1-Corpus/1.0"})
        with urllib.request.urlopen(dl_req, timeout=45) as dl, open(dest + ".tmp", "wb") as out:
            out.write(dl.read())
        os.replace(dest + ".tmp", dest)
        print(f"[+] Downloaded {apk_name} ({round(os.path.getsize(dest) / (1024 * 1024), 2)} MB)")
        return dest
    except Exception:
        tmp = os.path.join(uploads_dir, f"{pkg}_tmp")
        if os.path.exists(tmp):
            os.remove(tmp)
        return None


def ensure_corpus_apks(target_count: int = 20) -> List[str]:
    """Ensures at least ``target_count`` valid F-Droid APKs exist in ``uploads/``."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    uploads_dir = os.path.join(base_dir, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    existing = sorted(f for f in os.listdir(uploads_dir) if f.endswith(".apk"))
    if len(existing) >= target_count:
        return [os.path.join(uploads_dir, f) for f in existing]

    candidates = [e["package"] for e in FDROID_CORPUS_25] + EXTRA_FDROID_CANDIDATES
    seen = set()
    ordered = [c for c in candidates if not (c in seen or seen.add(c))]

    downloaded = [os.path.join(uploads_dir, f) for f in existing]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch_apk, pkg, uploads_dir) for pkg in ordered]
        for fut in concurrent.futures.as_completed(futures):
            path = fut.result()
            if path and path not in downloaded:
                downloaded.append(path)
            if len(downloaded) >= target_count + 5:
                break

    final_apks = sorted(os.path.join(uploads_dir, f) for f in os.listdir(uploads_dir) if f.endswith(".apk"))
    print(f"[+] Corpus APK count ready in uploads/: {len(final_apks)}")
    return final_apks


if __name__ == "__main__":
    ensure_corpus_apks(target_count=20)
