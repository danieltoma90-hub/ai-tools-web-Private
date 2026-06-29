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
