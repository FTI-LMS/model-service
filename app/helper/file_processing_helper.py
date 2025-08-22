import os

import requests
from fastapi import FastAPI, HTTPException
import shutil

GRAPH = "https://graph.microsoft.com/v1.0"


def _download_stream(token: str, drive_id: str, item_id: str, dest_path: str) -> int:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    tmp_path = dest_path + ".part"
    # Stream the file
    with requests.get(
            f"{GRAPH}/drives/{drive_id}/items/{item_id}/content",
            headers={"Authorization": f"Bearer {token}"},
            stream=True,
            timeout=60,
    ) as r:
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="File not found (did you pass a folder itemId?).")
    try:
        ct = r.headers.get("Content-Length")
        print(f"[download] content-length={ct}")
        r.raise_for_status()

        if hasattr(r.raw, "decode_content"):
             r.raw.decode_content = True
    except requests.HTTPError as e:
        raise HTTPException(status_code=r.status_code, detail=r.text or str(e))
    total = 0
    with open(tmp_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=64 * 1024):  # 4MB chunks
            if chunk:
                f.write(chunk)
                total += len(chunk)

    if total == 0:

        # Fallback A: sometimes iter_content yields nothing; try raw read
        try:
            with open(tmp_path, "wb") as f:
                shutil.copyfileobj(r.raw, f, length=1024 * 1024)
            total = os.path.getsize(tmp_path)
        except Exception as e:
            print(f"[download] raw fallback failed: {e}")

    if total == 0:
        # Fallback B: re-request without streaming and write content directly
        r2 = requests.get(
            f"{GRAPH}/drives/{drive_id}/items/{item_id}/content",
            headers={"Authorization": f"Bearer {token}", "Accept": "*/*"},
            timeout=60,
            allow_redirects=True,
            stream=False,
        )

        try:
            r2.raise_for_status()
        except Exception:
            print("[download] non-stream body (first 200):", r2.text[:200])
            raise

        with open(tmp_path, "wb") as f:
            f.write(r2.content)
        total = len(r2.content)

    shutil.move(tmp_path, dest_path)

    print(f"[download] wrote {total} bytes → {dest_path}")
    return total


def _get_item_name(token: str, drive_id: str, item_id: str) -> str:
    r = requests.get(
        f"{GRAPH}/drives/{drive_id}/items/{item_id}?select=name",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="Item not found in drive.")
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        raise HTTPException(status_code=r.status_code, detail=r.text or str(e))
    data = r.json()
    name = data.get("name")
    if not name:
        raise HTTPException(status_code=502, detail="Could not resolve item name from Graph.")
    return name
