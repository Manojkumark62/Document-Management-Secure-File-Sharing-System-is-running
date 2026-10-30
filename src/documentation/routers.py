from fastapi import APIRouter, Depends, File, UploadFile, Query, status, BackgroundTasks
from fastapi.responses import FileResponse

from sqlalchemy.orm import Session

from src.database import get_db
from src.authentication.models import User
from src.dependencies.roles import require_roles

from src.documentation.schemas import UploadDocumentResponse, DocumentResponse, DocumentListResponse, DocumentShareRequest, DocumentShareResponse
from src.documentation.services import upload_documents, list_documents, get_accessible_document, get_document_for_download, delete_document, share_document, revoke_document_share

from src.utils.file_handler import get_storage_path
from src.utils.notifications import notify_upload_complete
from src.utils.redis import get_cached_json, invalidate_document_list_cache, set_cached_json

router = APIRouter(prefix="/documents", tags=["Document Management"])

@router.post("/upload", response_model=UploadDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(background_tasks: BackgroundTasks, files: list[UploadFile] = File(..., description="Upload one or more documents using the multipart field name 'files'."), current_user: User = Depends(require_roles("admin", "manager", "user")), db: Session = Depends(get_db)):
    result = await upload_documents(files, current_user, db)
    invalidate_document_list_cache()
    background_tasks.add_task(notify_upload_complete, current_user.email, current_user.id, len(files))
    return result


@router.get("/", response_model=DocumentListResponse)
def get_documents(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100), file_type: str | None = Query(None), sort_by: str = Query("created_at", pattern="^(created_at|filename|file_size)$"), sort_order: str = Query("desc", pattern="^(asc|desc)$"), current_user: User = Depends(require_roles("admin", "manager", "user", "viewer")), db: Session = Depends(get_db)):
    cache_key = f"document-list:{current_user.id}:{page}:{page_size}:{file_type or ''}:{sort_by}:{sort_order}"
    cached_documents = get_cached_json(cache_key)
    if cached_documents is not None:
        return cached_documents

    documents = list_documents(db, current_user, page, page_size, file_type, sort_by, sort_order)
    response = DocumentListResponse.model_validate(documents).model_dump(mode="json")
    set_cached_json(cache_key, response)
    return response


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, current_user: User = Depends(require_roles("admin", "manager", "user", "viewer")), db: Session = Depends(get_db)):
    return get_accessible_document(document_id, current_user, db)


@router.get("/{document_id}/download")
def download_document(document_id: int, current_user: User = Depends(require_roles("admin", "manager", "user", "viewer")), db: Session = Depends(get_db)):
    document = get_document_for_download(document_id, current_user, db)
    file_path = get_storage_path(document.stored_filename)
    return FileResponse(path=file_path, media_type=document.content_type, filename=document.original_filename)


@router.delete("/{document_id}")
def remove_document(document_id: int, current_user: User = Depends(require_roles("admin", "manager", "user")), db: Session = Depends(get_db)):
    result = delete_document(document_id, current_user, db)
    invalidate_document_list_cache()
    return result


@router.post("/{document_id}/share", response_model=DocumentShareResponse)
def share_document_with_user(document_id: int, data: DocumentShareRequest, current_user: User = Depends(require_roles("admin", "manager", "user")), db: Session = Depends(get_db)):
    result = share_document(db, document_id, data.user_id, current_user)
    invalidate_document_list_cache()
    return result


@router.delete("/{document_id}/share/{user_id}", response_model=DocumentShareResponse)
def revoke_document_share_from_user(document_id: int, user_id: int, current_user: User = Depends(require_roles("admin", "manager", "user")), db: Session = Depends(get_db)):
    result = revoke_document_share(db, document_id, user_id, current_user)
    invalidate_document_list_cache()
    return result