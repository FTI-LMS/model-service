from __future__ import annotations
import base64, json, os, time
from urllib.parse import urlparse
from typing import Optional

import requests
from fastapi import FastAPI, Header, HTTPException, APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel
import jwt
from jwt import PyJWKClient

app = FastAPI(title="Graph Delegated API (no secrets)")

router = APIRouter()

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


class DownloadReq(BaseModel):
    # Option A: user's OneDrive path (e.g., "/Videos/lesson1.mp4")
    user_drive_path: Optional[str] = None
    # Option B: SharePoint site + path inside default Documents library
    site_url: Optional[str] = None  # e.g. https://contoso.sharepoint.com/sites/Training
    drive_path: Optional[str] = None  # e.g. /Shared Documents/Videos/lesson1.mp4



