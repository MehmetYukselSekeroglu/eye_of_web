#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live HTML match report writer for realtime camera search.

- Writes /home/user/Masaüstü/eye_of_web/src/reports.html (prepend newest row).
- Column discovery via information_schema: if the live "ImageBasedMain" has
  metadata/instagram_link/linkedin_link (or similar) columns beyond the
  schema.sql baseline, they are included automatically; otherwise URL is
  reconstructed from BaseDomainID+UrlPathID+UrlEtcID and platform inferred
  from the domain.
- Background worker thread so HTML I/O never blocks the Qt/search loop.
"""

import html
import os
import queue
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras


REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reports.html",
)

_MARKER = "<!-- MATCHES -->"

_SCAFFOLD = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="2">
<title>EyeOfWeb - Canl&#305; E&#351;le&#351;me Raporu</title>
<style>
 body{font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#0b0f14;color:#e6edf3;margin:0;padding:18px}
 h1{margin:0 0 6px;font-size:18px;color:#7ee787}
 .sub{color:#8b949e;font-size:12px;margin-bottom:14px}
 table{width:100%;border-collapse:collapse;font-size:13px}
 thead th{background:#161b22;color:#c9d1d9;text-align:left;padding:8px 10px;border-bottom:1px solid #30363d;position:sticky;top:0}
 tbody td{padding:8px 10px;border-bottom:1px solid #21262d;vertical-align:top}
 tbody tr:nth-child(odd){background:#0d1117}
 tbody tr:nth-child(even){background:#11161d}
 a{color:#58a6ff;text-decoration:none;margin-right:6px}
 a:hover{text-decoration:underline}
 .pill{display:inline-block;padding:1px 6px;border-radius:10px;font-size:11px;margin-right:4px}
 .ig{background:#3f1d38;color:#ffb6de}
 .li{background:#14375a;color:#a6d5ff}
 .fb{background:#1d2d4d;color:#9bb6ef}
 .tw{background:#1f2937;color:#dbe4ee}
 .yt{background:#3a1414;color:#ffb3b3}
 .web{background:#22272e;color:#adbac7}
 .score{font-weight:700}
 .s90{color:#7ee787}.s80{color:#79c0ff}.s70{color:#e3b341}.sLow{color:#ffa657}
 .id{font-family:ui-monospace,monospace;color:#e3b341}
 .when{color:#8b949e;font-size:11px}
 .empty{color:#8b949e;font-style:italic;padding:20px;text-align:center}
</style>
</head>
<body>
<h1>&#128065; Face ID Metadata Raporu</h1>
<div class="sub">Canl&#305; kamera e&#351;le&#351;meleri &mdash; en yeni en &uuml;stte. Sayfa 2 saniyede bir yenilenir.</div>
<table>
<thead><tr><th>Kimlik / G&ouml;rsel</th><th>Detay / Bilgi</th><th>Sosyal Linkler</th><th>Skor &amp; Zaman</th></tr></thead>
<tbody>
""" + _MARKER + """
<tr class="placeholder"><td colspan="4" class="empty">Hen&uuml;z e&#351;le&#351;me yok. Kamera bir y&uuml;z tan&#305;d&#305;&#287;&#305;nda bu alan canl&#305; olarak dolacak.</td></tr>
</tbody>
</table>
</body>
</html>
"""


_file_lock = threading.Lock()
_work_queue: "queue.Queue" = queue.Queue(maxsize=512)
_worker_thread = None
_worker_stop = threading.Event()
_column_cache = None
_column_cache_lock = threading.Lock()


OPTIONAL_COLUMN_CANDIDATES = {
    # match names people commonly use; we store lowercase keys, but query
    # preserves the original case via information_schema lookup
    "metadata",
    "instagram_link",
    "linkedin_link",
    "facebook_link",
    "twitter_link",
    "youtube_link",
    "isim",
    "name",
    "description",
    "aciklama",
    "profile_url",
}


def ensure_report_scaffold():
    """Create reports.html with the scaffold if it does not exist."""
    with _file_lock:
        if os.path.exists(REPORT_PATH):
            return
        tmp = REPORT_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(_SCAFFOLD)
        os.replace(tmp, REPORT_PATH)


def _get_db_config():
    from lib.load_config import load_config_from_file
    return load_config_from_file()[1]["database_config"]


def _open_connection():
    c = _get_db_config()
    conn = psycopg2.connect(
        host=c["host"], port=c["port"], dbname=c["database"],
        user=c["user"], password=c["password"],
    )
    conn.autocommit = True
    return conn


def _discover_optional_columns(conn):
    global _column_cache
    with _column_cache_lock:
        if _column_cache is not None:
            return _column_cache
        found = {}
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s",
                ("ImageBasedMain",),
            )
            present = {r[0] for r in cur.fetchall()}
        for col in present:
            if col.lower() in OPTIONAL_COLUMN_CANDIDATES:
                found[col.lower()] = col
        _column_cache = found
        return found


def _classify_platform(domain):
    if not domain:
        return ("web", "WEB")
    d = domain.lower()
    if "instagram" in d:
        return ("ig", "IG")
    if "linkedin" in d:
        return ("li", "LI")
    if "facebook" in d or "fb.com" in d:
        return ("fb", "FB")
    if "twitter" in d or d == "x.com" or d.endswith(".x.com"):
        return ("tw", "X")
    if "youtube" in d or "youtu.be" in d:
        return ("yt", "YT")
    return ("web", "WEB")


def _safe_href(url):
    try:
        p = urlparse(url)
    except Exception:
        return None
    if p.scheme not in ("http", "https"):
        return None
    if not p.netloc:
        return None
    return url


def _fetch_match_rows(conn, milvus_id, optional_cols):
    """Return a list of (face_id, image_meta_dict) for a Milvus hit."""
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            'SELECT "ID" FROM "EyeOfWebFaceID" WHERE "MilvusRefID" = %s',
            (milvus_id,),
        )
        rec = cur.fetchone()
        if not rec:
            return None, []
        face_id = rec["ID"]

        base_cols = [
            '"ID"', '"Protocol"', '"BaseDomainID"', '"UrlPathID"',
            '"UrlEtcID"', '"ImageTitleID"', '"ImageID"', '"DetectionDate"',
            '"RiskLevel"', '"Source"',
        ]
        extra = [f'"{real}"' for real in optional_cols.values()]
        select_list = ", ".join(base_cols + extra)
        q = (
            f'SELECT {select_list} FROM "ImageBasedMain" '
            'WHERE "FaceID" @> ARRAY[%s]::bigint[] '
            'ORDER BY "DetectionDate" DESC NULLS LAST LIMIT 1'
        )
        cur.execute(q, (face_id,))
        row = cur.fetchone()
        if row is None:
            # fallback ANY() form
            q2 = (
                f'SELECT {select_list} FROM "ImageBasedMain" '
                'WHERE %s = ANY("FaceID") LIMIT 1'
            )
            cur.execute(q2, (face_id,))
            row = cur.fetchone()
        if row is None:
            return face_id, {}

        meta = dict(row)

        # Resolve JOIN-able IDs to text
        def _lookup(table, col, value):
            if value is None:
                return None
            cur.execute(f'SELECT "{col}" FROM "{table}" WHERE "ID" = %s', (value,))
            r = cur.fetchone()
            return r[0] if r else None

        meta["_domain"] = _lookup("BaseDomainID", "Domain", meta.get("BaseDomainID"))
        meta["_path"] = _lookup("UrlPathID", "Path", meta.get("UrlPathID"))
        meta["_etc"] = _lookup("UrlEtcID", "Etc", meta.get("UrlEtcID"))
        meta["_title"] = _lookup("ImageTitleID", "Title", meta.get("ImageTitleID"))

        return face_id, meta


def _reconstruct_url(meta):
    proto = meta.get("Protocol") or "https"
    domain = meta.get("_domain")
    if not domain:
        return None
    path = meta.get("_path") or ""
    etc = meta.get("_etc") or ""
    if path and not path.startswith("/"):
        path = "/" + path
    return _safe_href(f"{proto}://{domain}{path}{etc}")


def _score_class(sim):
    if sim >= 0.9:
        return "s90"
    if sim >= 0.8:
        return "s80"
    if sim >= 0.7:
        return "s70"
    return "sLow"


def _build_row_html(face_id, similarity, meta, optional_cols):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    score_pct = max(0.0, min(1.0, float(similarity))) * 100
    score_cls = _score_class(similarity)

    # cell 1: id
    face_id_txt = html.escape(str(face_id) if face_id is not None else "-")
    cell_id = f'<span class="id">FaceID #{face_id_txt}</span>'

    # cell 2: detail (title / name / metadata)
    detail_parts = []
    # prefer optional 'name'/'isim'
    for key in ("isim", "name"):
        if key in optional_cols and meta.get(optional_cols[key]):
            detail_parts.append(f"<strong>{html.escape(str(meta[optional_cols[key]]))}</strong>")
            break
    if meta.get("_title"):
        detail_parts.append(html.escape(str(meta["_title"])))
    for key in ("description", "aciklama", "metadata"):
        if key in optional_cols and meta.get(optional_cols[key]):
            val = str(meta[optional_cols[key]])
            if len(val) > 220:
                val = val[:217] + "..."
            detail_parts.append(f"<div class=\"when\">{html.escape(val)}</div>")
            break
    if meta.get("RiskLevel"):
        detail_parts.append(f'<div class="when">risk: {html.escape(str(meta["RiskLevel"]))}</div>')
    if not detail_parts:
        detail_parts.append('<span class="when">(bilgi yok)</span>')
    cell_detail = "<br>".join(detail_parts)

    # cell 3: links
    links = []
    url_columns = [
        ("instagram_link", "ig", "IG"),
        ("linkedin_link", "li", "LI"),
        ("facebook_link", "fb", "FB"),
        ("twitter_link", "tw", "X"),
        ("youtube_link", "yt", "YT"),
        ("profile_url", None, None),
    ]
    for key, cls, label in url_columns:
        if key not in optional_cols:
            continue
        val = meta.get(optional_cols[key])
        if not val:
            continue
        href = _safe_href(str(val))
        if not href:
            continue
        if cls is None:
            cls, label = _classify_platform(urlparse(href).netloc)
        links.append(
            f'<a class="pill {cls}" href="{html.escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">{label}</a>'
        )
    reconstructed = _reconstruct_url(meta)
    if reconstructed:
        cls, label = _classify_platform(urlparse(reconstructed).netloc)
        links.append(
            f'<a class="pill {cls}" href="{html.escape(reconstructed, quote=True)}" target="_blank" rel="noopener noreferrer">{label}</a>'
        )
    if not links:
        links.append('<span class="when">link yok</span>')
    cell_links = "".join(links)

    # cell 4: score + time
    cell_score = (
        f'<span class="score {score_cls}">%{score_pct:.1f}</span>'
        f'<div class="when">{html.escape(now)}</div>'
    )

    return (
        "<tr>"
        f"<td>{cell_id}</td>"
        f"<td>{cell_detail}</td>"
        f"<td>{cell_links}</td>"
        f"<td>{cell_score}</td>"
        "</tr>"
    )


def _prepend_row(row_html):
    with _file_lock:
        if not os.path.exists(REPORT_PATH):
            with open(REPORT_PATH + ".tmp", "w", encoding="utf-8") as f:
                f.write(_SCAFFOLD)
            os.replace(REPORT_PATH + ".tmp", REPORT_PATH)

        with open(REPORT_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        if _MARKER not in content:
            # corrupt/old file -> rewrite scaffold, preserving nothing to avoid
            # further corruption. This only fires if a user hand-edited the file.
            content = _SCAFFOLD

        # Drop placeholder row if present
        content = content.replace(
            '<tr class="placeholder"><td colspan="4" class="empty">Hen&uuml;z e&#351;le&#351;me yok. Kamera bir y&uuml;z tan&#305;d&#305;&#287;&#305;nda bu alan canl&#305; olarak dolacak.</td></tr>\n',
            "",
        )

        new_content = content.replace(_MARKER, _MARKER + "\n" + row_html, 1)

        tmp = REPORT_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new_content)
        os.replace(tmp, REPORT_PATH)


def _worker_loop():
    conn = None
    backoff = 1.0
    while not _worker_stop.is_set():
        try:
            item = _work_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        if item is None:
            break
        milvus_id, similarity = item
        try:
            if conn is None or conn.closed:
                conn = _open_connection()
                backoff = 1.0
            optional_cols = _discover_optional_columns(conn)
            face_id, meta = _fetch_match_rows(conn, milvus_id, optional_cols)
            row_html = _build_row_html(face_id, similarity, meta, optional_cols)
            _prepend_row(row_html)
        except Exception as e:
            # Never let report failures impact the search pipeline.
            print(f"[report_writer] error on milvus_id={milvus_id}: {e}")
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
            conn = None
            time.sleep(backoff)
            backoff = min(backoff * 2, 15.0)
        finally:
            _work_queue.task_done()


def start_worker():
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    _worker_stop.clear()
    _worker_thread = threading.Thread(
        target=_worker_loop, name="report_writer", daemon=True
    )
    _worker_thread.start()


def stop_worker():
    _worker_stop.set()
    try:
        _work_queue.put_nowait(None)
    except queue.Full:
        pass


def queue_match(milvus_id, similarity):
    """Non-blocking: drop the match onto the worker queue."""
    try:
        _work_queue.put_nowait((milvus_id, float(similarity)))
    except queue.Full:
        # Queue is 512 deep; if it overflows, silently drop rather than
        # backpressure the camera pipeline.
        pass
