from fastapi import Depends
from app.api.deps import get_video_processor
from app.dto.file_processing_request import FileProcessingRequest
from app.dto.file_processing_response import FileProcessingResponse
from app.helper.file_processing_helper import _get_item_name, _download_stream
from app.services.video_file_invoker import *
from app.services.video_file_invoker import _bearer_to_token
from app.services.video_processor import VideoProcessor
from pathlib import Path

router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FILES_DIR = PROJECT_ROOT/"files"
os.makedirs(FILES_DIR, exist_ok=True)

@router.get("/whoami")
def whoami(authorization: str = Header(...)):
    token = _bearer_to_token(authorization)
    #claims = validate_graph_token(token)
    me = graph_get("/me", token).json()
    return {"me": me}


@router.get("/files")
def list_my_root_files(authorization: str = Header(...)):
    token = _bearer_to_token(authorization)
    #validate_graph_token(token)
    items = graph_get("/me/drive/root/children", token).json()
    return items

@router.post("/processFile")
def process_file(req: FileProcessingRequest, authorization: str = Header(...), video_processor: VideoProcessor = Depends(get_video_processor),):
    token = _bearer_to_token(authorization)
    filename = req.filename or _get_item_name(req.token, req.driveId, req.itemId)
    # Normalize filename (basic safety: no path traversal)
    filename = os.path.basename(filename).strip()

    if not filename:
        raise HTTPException(status_code=400, detail="Filename resolved to empty.")

    dest_path = os.path.join(FILES_DIR, filename)
    # Download
    try:
        size = _download_stream(token, req.driveId, req.itemId, dest_path)
    except HTTPException:
      # make sure partial file is cleaned if present
      part = dest_path + ".part"
      if os.path.exists(part):
         try:
            os.remove(part)
         except:
           pass
      raise
    try:
      result = video_processor.process_file(dest_path)
    except Exception as e:
      raise HTTPException(status_code=500, detail=f"Processing failed: {e}")
    finally:
      if os.path.exists(dest_path):
          os.remove(dest_path)


    return FileProcessingResponse(**result)