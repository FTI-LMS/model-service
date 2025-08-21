import os
import shutil
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

GRAPH = "https://graph.microsoft.com/v1.0"
FILES_DIR = os.path.join(os.path.dirname(__file__), "files")
os.makedirs(FILES_DIR, exist_ok=True)

app = FastAPI(title="Graph File Downloader", version="1.0.0")


# ----------- Models -----------

class FileProcessingRequest(BaseModel):
    driveId: str = Field(..., description="Drive ID of the SharePoint/OneDrive library")
    itemId: str = Field(..., description="Drive item ID (file)")
    filename: Optional[str] = Field(
    None,
    description="Filename to save as (if omitted, the item's original name is used)"
)
