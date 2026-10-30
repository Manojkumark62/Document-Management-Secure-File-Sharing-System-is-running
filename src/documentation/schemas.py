from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class DocumentResponse(BaseModel):
    id: int
    original_filename: str
    stored_filename: str
    content_type: str
    file_size: int
    file_extension: str
    owner_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadDocumentResponse(BaseModel):
    message: str
    total_uploaded: int
    documents: list[DocumentResponse]


class DocumentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    documents: list[DocumentResponse]


class DocumentShareRequest(BaseModel):
    user_id: int = Field(gt=0)


class DocumentShareResponse(BaseModel):
    message: str
    document_id: int
    user_id: int