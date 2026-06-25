from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client
import os

_security = HTTPBearer()

def get_supabase():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"]
    )

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(_security)):
    token = credentials.credentials
    try:
        sb = get_supabase()
        user = sb.auth.get_user(token)
        return user.user
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalid sau expirat")
