import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from auth import get_supabase

BUCKET = "documents"
ALLOWED_TOOLS = {"minuta", "mockup", "scenarii"}
UPLOADS_BUCKET = "uploads"
UPLOAD_TOOLS_EXT = {"scenarii": {".docx"}, "mockup": {".docx", ".xlsx"}}
UPLOAD_MAX_BYTES = 52_428_800  # 50MB — maximul planului free Supabase


def _safe_filename(filename: str) -> str:
    """Strip path separators and dangerous sequences; keep only the basename."""
    name = Path(filename).name
    if not name or ".." in name or re.search(r"[/\\:\x00]", name):
        raise ValueError(f"Filename invalid: {filename!r}")
    return name


def _safe_email(email: str) -> str:
    """Sanitize email address for use as a storage path component."""
    clean = re.sub(r"[^\w.\-@]", "_", email).strip("_")
    return clean or "anonymous"


def upload_file(local_path: Path, tool: str, filename: str, user_email: str = "anonymous") -> str:
    """Uploadează fișierul în Supabase Storage sub {tool}/{user_email}/{filename}."""
    if tool not in ALLOWED_TOOLS:
        raise ValueError(f"Tool necunoscut: {tool!r}")
    safe_name = _safe_filename(filename)
    safe_owner = _safe_email(user_email)
    sb = get_supabase()
    storage_path = f"{tool}/{safe_owner}/{safe_name}"
    with open(local_path, "rb") as f:
        sb.storage.from_(BUCKET).upload(storage_path, f, {"upsert": "true"})
    return storage_path


def list_files(tool: str | None = None) -> list[dict]:
    """Listează fișierele din bucket, opțional filtrate pe tool.

    Structura bucket: {tool}/{user_email}/{filename}
    Acceptă și vechea structură flat {tool}/{filename} (legacy).
    """
    sb = get_supabase()
    tools = [tool] if tool else sorted(ALLOWED_TOOLS)
    all_files = []

    for t in tools:
        try:
            items = sb.storage.from_(BUCKET).list(t)
        except Exception:
            continue

        for item in items:
            name = item.get("name", "")
            if not name:
                continue
            meta = item.get("metadata") or {}
            if meta.get("size"):
                # Fisier direct in folderul tool (structura legacy flat)
                item["tool"] = t
                item["owner"] = "—"
                item["storage_path"] = f"{t}/{name}"
                all_files.append(item)
            else:
                # Subfolder = email utilizator; listam fisierele din interior
                owner_email = name
                try:
                    sub_items = sb.storage.from_(BUCKET).list(f"{t}/{owner_email}")
                except Exception:
                    continue
                for f in sub_items:
                    if not f.get("name") or not (f.get("metadata") or {}).get("size"):
                        continue
                    f["tool"] = t
                    f["owner"] = owner_email
                    f["storage_path"] = f"{t}/{owner_email}/{f['name']}"
                    all_files.append(f)

    return sorted(all_files, key=lambda x: x.get("created_at", ""), reverse=True)


def get_signed_url(storage_path: str, expires_in: int = 3600) -> str:
    """Generează URL temporar de download (valid expires_in secunde)."""
    sb = get_supabase()
    result = sb.storage.from_(BUCKET).create_signed_url(storage_path, expires_in)
    return result["signedURL"]


def delete_file(storage_path: str) -> None:
    """Șterge un fișier din Supabase Storage."""
    sb = get_supabase()
    sb.storage.from_(BUCKET).remove([storage_path])


_uploads_bucket_ready = False


def ensure_uploads_bucket() -> None:
    """Creează bucket-ul privat 'uploads' dacă lipsește. Idempotent, memoizat per proces.

    Curăță best-effort obiectele orfane mai vechi de 24h (upload-uri abandonate
    înainte de estimate — fluxul normal șterge obiectul la download).
    """
    global _uploads_bucket_ready
    if _uploads_bucket_ready:
        return
    sb = get_supabase()
    existing = {getattr(b, "name", None) or getattr(b, "id", "") for b in sb.storage.list_buckets()}
    if UPLOADS_BUCKET not in existing:
        sb.storage.create_bucket(
            UPLOADS_BUCKET,
            options={"public": False, "file_size_limit": UPLOAD_MAX_BYTES},
        )
    _cleanup_old_uploads(sb)
    _uploads_bucket_ready = True


def _cleanup_old_uploads(sb, max_age_hours: int = 24) -> None:
    """Șterge obiectele orfane mai vechi de max_age_hours din bucket-ul uploads. Best-effort."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    for folder in UPLOAD_TOOLS_EXT:
        try:
            items = sb.storage.from_(UPLOADS_BUCKET).list(folder)
        except Exception:
            continue
        stale = []
        for item in items:
            created = item.get("created_at", "")
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                continue
            if created_dt < cutoff:
                stale.append(f"{folder}/{item['name']}")
        if stale:
            try:
                sb.storage.from_(UPLOADS_BUCKET).remove(stale)
            except Exception:
                pass


def create_upload_url(tool: str, filename: str) -> dict:
    """URL semnat de upload pentru fișierul-sursă al unui tool. Obiect: {tool}/{uuid}{ext}."""
    allowed = UPLOAD_TOOLS_EXT.get(tool)
    if allowed is None:
        raise ValueError(f"Tool necunoscut pentru upload: {tool!r}")
    ext = Path(_safe_filename(filename)).suffix.lower()
    if ext not in allowed:
        raise ValueError(f"Extensie neacceptată pentru {tool}: {ext or '(fără extensie)'}")

    ensure_uploads_bucket()
    storage_path = f"{tool}/{uuid.uuid4().hex}{ext}"
    sb = get_supabase()
    signed = sb.storage.from_(UPLOADS_BUCKET).create_signed_upload_url(storage_path)
    return {
        "storage_path": storage_path,
        "signed_url": signed["signed_url"],
        "token": signed["token"],
    }


def download_upload(storage_path: str) -> Path:
    """Descarcă un fișier-sursă din bucket-ul 'uploads' într-un temp local și șterge obiectul.

    Storage-ul e releu, nu depozit: după descărcare obiectul dispare (best-effort).
    """
    parts = storage_path.split("/")
    allowed_exts = {ext for exts in UPLOAD_TOOLS_EXT.values() for ext in exts}
    if (
        len(parts) != 2
        or parts[0] not in UPLOAD_TOOLS_EXT
        or parts[1] in ("", ".", "..")
        or "%" in storage_path
        or "\\" in storage_path
        or Path(parts[1]).suffix.lower() not in allowed_exts
    ):
        raise ValueError(f"Cale de upload invalidă: {storage_path!r}")

    sb = get_supabase()
    data = sb.storage.from_(UPLOADS_BUCKET).download(storage_path)

    fd, tmp_name = tempfile.mkstemp(suffix=Path(storage_path).suffix)
    os.close(fd)
    path = Path(tmp_name)
    path.write_bytes(data)

    try:
        sb.storage.from_(UPLOADS_BUCKET).remove([storage_path])
    except Exception:
        pass  # obiect orfan — inofensiv, bucketul e doar releu
    return path
