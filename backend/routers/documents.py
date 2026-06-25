from fastapi import APIRouter, Depends
from auth import verify_token
from storage import list_files, get_signed_url

router = APIRouter()


@router.get("/documents")
def get_documents(tool: str | None = None, user=Depends(verify_token)):
    files = list_files(tool=tool)
    result = []
    for f in files:
        storage_path = f"{tool}/{f['name']}" if tool else f["name"]
        result.append({
            "name": f["name"],
            "created_at": f.get("created_at", ""),
            "size": f.get("metadata", {}).get("size", 0),
            "download_url": get_signed_url(storage_path),
        })
    return result
