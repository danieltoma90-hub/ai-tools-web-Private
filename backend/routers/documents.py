from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from auth import verify_token
from storage import ALLOWED_TOOLS, list_files, get_signed_urls, get_storage_usage, delete_file

router = APIRouter()


@router.get("/storage/usage")
def storage_usage(user=Depends(verify_token)):
    """Spațiul ocupat vs cota Supabase — pentru alerta de curățenie din Repository."""
    return get_storage_usage()


@router.get("/dashboard/summary")
def dashboard_summary(user=Depends(verify_token)):
    """Datele paginii Acasă într-un singur apel: o singură listare (refolosită
    și la usage) și URL-uri semnate doar pentru cele 5 documente recente."""
    files = list_files()

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    week_count = 0
    for f in files:
        raw = f.get("created_at", "")
        try:
            if datetime.fromisoformat(raw.replace("Z", "+00:00")) > week_ago:
                week_count += 1
        except (ValueError, TypeError):
            continue

    recent = files[:5]
    try:
        urls = get_signed_urls([f.get("storage_path", "") for f in recent])
    except Exception:
        urls = {}

    return {
        "total_documents": len(files),
        "week_count": week_count,
        "usage": get_storage_usage(documents_files=files),
        "documents": [
            {
                "name": f["name"],
                "tool": f.get("tool", ""),
                "owner": f.get("owner", "—"),
                "created_at": f.get("created_at", ""),
                "download_url": urls.get(f.get("storage_path", ""), ""),
            }
            for f in recent
        ],
    }


@router.get("/documents")
def get_documents(
    tool: str | None = None,
    limit: int | None = None,
    user=Depends(verify_token),
):
    """Documentele generate, cel mai recent primul.

    `limit` taie lista INAINTE de semnare: panoul „Recent" cere 5 fisiere, iar
    semnarea celorlalte cateva sute ar fi munca aruncata.
    """
    if tool is not None and tool not in ALLOWED_TOOLS:
        raise HTTPException(status_code=422, detail=f"Tool necunoscut: {tool}")
    if limit is not None and limit < 1:
        raise HTTPException(status_code=422, detail="limit trebuie să fie cel puțin 1")

    files = list_files(tool=tool)
    if limit is not None:
        files = files[:limit]
    paths = [f.get("storage_path", "") for f in files]
    try:
        urls = get_signed_urls(paths)
    except Exception:
        urls = {}
    result = []
    for f in files:
        storage_path = f.get("storage_path", "")
        result.append({
            "name": f["name"],
            "tool": f.get("tool", ""),
            "owner": f.get("owner", "—"),
            "storage_path": storage_path,
            "created_at": f.get("created_at", ""),
            "size": (f.get("metadata") or {}).get("size", 0),
            "download_url": urls.get(storage_path, ""),
        })
    return result


@router.delete("/documents")
def delete_document(storage_path: str, user=Depends(verify_token)):
    """Șterge un document din Supabase Storage.
    Utilizatorul poate șterge doar propriile documente (email-ul este în path).
    """
    # verify_token returnează obiect supabase User, nu dict — .get() ar crăpa
    user_email = getattr(user, "email", None) or ""
    # Verifică că path-ul conține email-ul utilizatorului curent
    if user_email and f"/{user_email}/" not in storage_path and f"/{user_email.replace('@', '%40')}/" not in storage_path:
        raise HTTPException(status_code=403, detail="Nu poți șterge documentele altora")
    try:
        delete_file(storage_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}
