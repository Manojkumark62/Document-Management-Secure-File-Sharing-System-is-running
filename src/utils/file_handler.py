import os
import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from dotenv import load_dotenv

load_dotenv()
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads")).resolve()
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "5242880"))
ALLOWED_TYPES = {".pdf": {"application/pdf"}, ".txt": {"text/plain"}, ".png": {"image/png"}, ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}}

def validate_file(filename: str, content_type: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"File extension not allowed: {extension}")
    if content_type not in ALLOWED_TYPES[extension]:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Content type does not match the allowed file type")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty files are not allowed")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File size exceeds the 5 MB limit")
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PDF file signature")
    if extension == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PNG file signature")
    if extension in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JPEG file signature")
    if extension == ".txt" and b"\x00" in content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid text file content")
    return extension

def generate_unique_filename(extension: str) -> str:
    return f"{uuid.uuid4().hex}{extension}"

def get_storage_path(filename: str) -> Path:
    path = (UPLOAD_DIR / filename).resolve()
    if path.parent != UPLOAD_DIR:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid storage path")
    return path

def ensure_upload_directory() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)