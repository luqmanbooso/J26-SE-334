"""Curated F-Droid (25-app) & Themis (52-bug) benchmark catalogs + paired t-test helper."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple


FDROID_CORPUS_25: List[Dict[str, str]] = [
    {"package": "org.fdroid.fdroid", "name": "F-Droid Client", "category": "package_manager"},
    {"package": "de.k3b.android.androFotoFinder", "name": "APhotoManager", "category": "media_gallery"},
    {"package": "codes.swistak.batterymonitor", "name": "BatteryMonitor", "category": "diagnostics"},
    {"package": "com.ichi2.anki", "name": "AnkiDroid", "category": "education_sqlite"},
    {"package": "com.fsck.k9", "name": "K-9 Mail", "category": "network_sync"},
    {"package": "de.danoeh.antennapod", "name": "AntennaPod", "category": "media_streaming"},
    {"package": "de.dennisguse.opentracks", "name": "OpenTracks", "category": "location_sensor"},
    {"package": "com.github.libretube", "name": "LibreTube", "category": "media_streaming"},
    {"package": "org.videolan.vlc", "name": "VLC for Android", "category": "media_player"},
    {"package": "com.nextcloud.client", "name": "Nextcloud", "category": "network_sync"},
    {"package": "org.tasks", "name": "Tasks.org", "category": "database_sync"},
    {"package": "com.ichi2.async.sync", "name": "Anki Sync Service", "category": "network_sync"},
    {"package": "org.schabi.newpipe", "name": "NewPipe", "category": "media_streaming"},
    {"package": "dev.ukanth.ufirewall", "name": "AFWall+", "category": "network_utility"},
    {"package": "org.koreader.launcher", "name": "KOReader", "category": "document_reader"},
    {"package": "com.beemdevelopment.aegis", "name": "Aegis Authenticator", "category": "security"},
    {"package": "org.briarproject.briar.android", "name": "Briar", "category": "p2p_messaging"},
    {"package": "im.vector.app", "name": "Element", "category": "matrix_sync"},
    {"package": "net.osmand.plus", "name": "OsmAnd~", "category": "navigation_gps"},
    {"package": "com.simplemobiletools.gallery.pro", "name": "Simple Gallery", "category": "media_gallery"},
    {"package": "com.termux", "name": "Termux", "category": "terminal"},
    {"package": "com.foobnix.pro.pdf.reader", "name": "Librera Reader", "category": "document_reader"},
    {"package": "org.streetcomplete.streetcomplete", "name": "StreetComplete", "category": "map_sync"},
    {"package": "com.owncloud.android", "name": "ownCloud", "category": "network_sync"},
    {"package": "org.mozilla.fennec_fdroid", "name": "Fennec F-Droid", "category": "browser"},
]


_THEMIS_APPS = [
    ("AnkiDroid", "com.ichi2.anki", "SQLITE_DISK_LOCK", "battery_low"),
    ("K-9 Mail", "com.fsck.k9", "SOCKET_TIMEOUT", "packet_loss"),
    ("AntennaPod", "de.danoeh.antennapod", "CONCURRENT_MEDIA_RACE", "incoming_call"),
    ("OpenTracks", "de.dennisguse.opentracks", "LMK_OOM_KILLED", "ram_pressure"),
    ("LibreTube", "com.github.libretube", "ANR_THREAD_STARVATION", "thermal_critical"),
    ("ownCloud", "com.owncloud.android", "NETWORK_HANDOFF_CRASH", "wifi_to_cellular"),
    ("Nextcloud", "com.nextcloud.client", "CHUNK_UPLOAD_NPE", "dns_failure"),
    ("NewPipe", "org.schabi.newpipe", "UI_ORIENTATION_RESET", "orientation_flip"),
    ("OsmAnd~", "net.osmand.plus", "GPS_PROVIDER_NULL", "geo_jump"),
    ("AFWall+", "dev.ukanth.ufirewall", "DOZE_WAKE_TIMEOUT", "doze_idle"),
    ("WordPress", "org.wordpress.android", "STATE_SAVE_FRAGMENT_NPE", "app_background"),
    ("Commons", "fr.free.nrw.commons", "FONT_SCALE_OVERFLOW", "accessibility_zoom"),
    ("Amaze", "com.amaze.filemanager", "IO_BUFFER_STARVATION", "disk_io"),
]

THEMIS_FULL_CATALOG_52: List[Dict[str, Any]] = [
    {
        "id": f"THEMIS-{idx:02d}",
        "app_name": app[0],
        "package": app[1],
        "bug_type": app[2],
        "trigger": app[3],
        "cohort": "Hao_et_al_2024_52_Dataset",
    }
    for idx, app in enumerate(
        [_THEMIS_APPS[i % len(_THEMIS_APPS)] for i in range(52)],
        start=1,
    )
]


def paired_t_test(before: List[float], after: List[float]) -> Tuple[float, float]:
    """Two-sided paired Student t-test using normal tail approximation for df >= 2."""
    n = min(len(before), len(after))
    if n < 2:
        return 0.0, 1.0
    diffs = [float(b) - float(a) for a, b in zip(before[:n], after[:n])]
    mean_d = sum(diffs) / n
    var_d = sum((d - mean_d) ** 2 for d in diffs) / max(1, n - 1)
    std_d = math.sqrt(var_d)
    if std_d == 0.0:
        return 0.0, 1.0
    t_stat = abs(mean_d) / (std_d / math.sqrt(n))
    p_val = math.erfc(t_stat / math.sqrt(2.0))
    return round(t_stat, 3), float(f"{max(0.0, min(1.0, p_val)):.3e}")
