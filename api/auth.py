from __future__ import annotations
import httpx
import jwt
import json
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from api.config import settings

security = HTTPBearer(auto_error=False)

_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache

    import base64
    try:
        pub_key = settings.clerk_publishable_key
        b64_part = pub_key.split("_", 2)[-1]
        padding = 4 - len(b64_part) % 4
        if padding != 4:
            b64_part += "=" * padding
        domain = base64.b64decode(b64_part).decode("utf-8").strip("$")
        jwks_url = f"https://{domain}/.well-known/jwks.json"
    except Exception:
        jwks_url = "https://clerk.com/.well-known/jwks.json"

    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url, timeout=10.0)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    """Verify Clerk JWT and return the user payload."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not settings.clerk_secret_key:
        raise HTTPException(status_code=503, detail="Auth not configured")

    token = credentials.credentials

    try:
        jwks = await _get_jwks()
        
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        
        public_key = None
        for key_data in jwks.get("keys", []):
            if key_data.get("kid") == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))
                break
        
        if not public_key:
            raise HTTPException(status_code=401, detail="Unable to find matching key")

        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_exp": True},
        )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        return {
            "user_id": user_id,
            "email": payload.get("email", ""),
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth failed: {str(e)}")


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict | None:
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None