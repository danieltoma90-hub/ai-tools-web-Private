from fastapi import APIRouter, Depends, HTTPException
from auth import verify_token
from storage import list_files, get_signed_url, delete_file

router = APIRouter()


@router.get("/documents")
def get_documents(tool: str | None = None, user=Depends(verify_token)):
    files = list_files(tool=tool)
    result = []
    for f in files:
        storage_path = f.get("storage_path", "")
        try:
            download_url = get_signed_url(storage_path)
        except Exception:
            download_url = ""
        result.append({
            "name": f["name"],
            "tool": f.get("tool", ""),
            "owner": f.get("owner", "—"),
            "storage_path": storage_path,
            "created_at": f.get("created_at", ""),
            "size": (f.get("metadata") or {}).get("size", 0),
            "download_url": download_url,
        })
    return result


@router.delete("/documents")
def delete_document(storage_path: str, user=Depends(verify_token)):
    """Șterge un document din Supabase Storage.
    Utilizatorul poate șterge doar propriile documente (email-ul este în path).
    """
    user_email = user.get("email", "")
    safe_owner = user_email.replace("@", "@")  # email as-is
    # Verifică că path-ul conține email-ul utilizatorului curent
    if user_email and f"/{user_email}/" not in storage_path and f"/{user_email.replace('@', '%40')}/" not in storage_path:
        raise HTTPException(status_code=403, detail="Nu poți șterge documentele altora")
    try:
        delete_file(storage_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}
