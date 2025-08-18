from __future__ import annotations
import base64, json, os, time
from urllib.parse import urlparse
from typing import Optional

import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import jwt
from jwt import PyJWKClient

app = FastAPI(title="Graph Delegated API (no secrets)")

# Acceptable audiences for Microsoft Graph tokens
GRAPH_AUDS = {
    "https://graph.microsoft.com",
    "00000003-0000-0000-c000-000000000000",  # Graph's app ID GUID sometimes used as aud
}


def _bearer_to_token(authorization: str) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1].strip()


def _peek_payload_noverify(token: str) -> dict:
    try:
        header_b64, payload_b64 = token.split(".")[0:2]

        def b64url_decode(s: str) -> bytes:
            s += "=" * (-len(s) % 4)
            return base64.urlsafe_b64decode(s.encode())

        return json.loads(b64url_decode(payload_b64))
    except Exception:
        raise HTTPException(401, "Malformed JWT")


def _issuer_from_token(token: str) -> str:
    payload = _peek_payload_noverify(token)
    iss = payload.get("iss")
    if not iss:
        raise HTTPException(401, "JWT has no issuer (iss)")
    return iss  # e.g. https://login.microsoftonline.com/<tenant-id>/v2.0


def _jwks_client_for_issuer(issuer: str) -> PyJWKClient:
    # Discover the JWKS URI dynamically from the issuer's OpenID config
    oidc_url = f"{issuer}/.well-known/openid-configuration"
    try:
        conf = requests.get(oidc_url, timeout=10).json()
        jwks_uri = conf["jwks_uri"]
    except Exception:
        raise HTTPException(502, "Failed to fetch OpenID configuration/JWKS")
    return PyJWKClient(jwks_uri)


def validate_graph_token(token: str) -> dict:
    issuer = _issuer_from_token(token)
    jwks = _jwks_client_for_issuer(issuer)
    try:
        signing_key = jwks.get_signing_key_from_jwt(token)
    except Exception:
        raise HTTPException(401, "Unable to resolve signing key for token")

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=list(GRAPH_AUDS),
            issuer=issuer,
            options={"require": ["iss", "aud", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidAudienceError:
        raise HTTPException(401, "Invalid audience (not a Graph token)")
    except jwt.InvalidIssuerError:
        raise HTTPException(401, "Invalid issuer")
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}")

    nbf = claims.get("nbf")
    if isinstance(nbf, int) and time.time() < nbf:
        raise HTTPException(401, "Token not yet valid")

    return claims


GRAPH = "https://graph.microsoft.com/v1.0"


def graph_get(path_or_url: str, token: str, *, stream: bool = False, timeout: int = 120) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"}
    url = path_or_url if path_or_url.startswith("http") else f"{GRAPH}{path_or_url}"
    r = requests.get(url, headers=headers, stream=stream, timeout=timeout)
    if r.status_code >= 400:

      try:
        detail = r.json()
      except Exception:
        detail = {"status": r.status_code, "body": r.text}
        raise HTTPException(r.status_code, detail)
    return r


@app.get("/whoami")
def whoami(authorization: str = Header(...)):
    token = _bearer_to_token(authorization)
    claims = validate_graph_token(token)
    me = graph_get("/me", token).json()
    return {"aud": claims.get("aud"), "tid": claims.get("tid"), "me": me}


@app.get("/files")
def list_my_root_files(authorization: str = Header(...)):
    token = _bearer_to_token(authorization)
    validate_graph_token(token)
    items = graph_get("/me/drive/root/children", token).json()
    return items


class DownloadReq(BaseModel):
    # Option A: user's OneDrive path (e.g., "/Videos/lesson1.mp4")
    user_drive_path: Optional[str] = None
    # Option B: SharePoint site + path inside default Documents library
    site_url: Optional[str] = None  # e.g. https://contoso.sharepoint.com/sites/Training
    drive_path: Optional[str] = None  # e.g. /Shared Documents/Videos/lesson1.mp4


@app.post("/download")
def download(req: DownloadReq, authorization: str = Header(...)):
    token = _bearer_to_token(authorization)
    validate_graph_token(token)
    os.makedirs("downloads", exist_ok=True)

    if req.user_drive_path:
        # User's OneDrive file
        url = f"/me/drive/root:{req.user_drive_path}:/content"
        filename = os.path.basename(req.user_drive_path)
    elif req.site_url and req.drive_path:
        # SharePoint file by site → resolve site id then fetch
        u = urlparse(req.site_url)
        site = graph_get(f"/sites/{u.netloc}:{u.path}", token).json()
        site_id = site["id"]
        url = f"/sites/{site_id}/drive/root:{req.drive_path}:/content"
        filename = os.path.basename(req.drive_path)
    else:
        raise HTTPException(400, "Provide either user_drive_path OR (site_url + drive_path)")

    resp = graph_get(url, token, stream=True, timeout=600)
    out_path = os.path.join("downloads", filename)
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(1024 * 1024):
            if chunk: f.write(chunk)

    return FileResponse(out_path, filename=filename)
