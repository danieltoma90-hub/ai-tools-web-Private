import re
from pathlib import Path
from auth import get_supabase

BUCKET = "documents"
ALLOWED_TOOLS = {"minuta", "mockup", "scenarii"}


def _safe_filename(filename: str) -> str:
    """Strip path separators and dangerous sequences; keep only the basename."""
    name = Path(filename).name
    if not name or ".." in name or re.search(r"[/\\:\x00]", name):
        raise ValueError(f"Filename invalid: {filename!r}")
    return name


def upload_file(local_path: Path, tool: str, filename: str) -> str:
    """Uploadează fișierul în Supabase Storage. Returnează calea în bucket: 'tool/filename'."""
    if tool not in ALLOWED_TOOLS:
        raise ValueError(f"Tool necunoscut: {tool!r}")
    safe_name = _safe_filename(filename)
    sb = get_supabase()
    storage_path = f"{tool}/{safe_name}"
    with open(local_path, "rb") as f:
        sb.storage.from_(BUCKET).upload(storage_path, f, {"upsert": "true"})
    return storage_path


def list_files(tool: str | None = None) -> list[dict]:
    """Listează fișierele din bucket, opțional filtrate pe tool. Sortate descrescător după dată."""
    sb = get_supabase()
    folder = tool or ""
    files = sb.storage.from_(BUCKET).list(folder)
    return sorted(files, key=lambda x: x.get("created_at", ""), reverse=True)


def get_signed_url(storage_path: str, expires_in: int = 3600) -> str:
    """Generează URL temporar de download (valid expires_in secunde)."""
    sb = get_supabase()
    result = sb.storage.from_(BUCKET).create_signed_url(storage_path, expires_in)
    return result["signedURL"]
