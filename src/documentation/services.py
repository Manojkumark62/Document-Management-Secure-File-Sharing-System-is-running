from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, or_
from src.authentication.models import User
from src.documentation.models import Document, document_shares
from src.roles.services import get_user_role_names
from src.documentation.schemas import DocumentResponse
from src.utils.file_handler import validate_file, generate_unique_filename, get_storage_path, ensure_upload_directory, MAX_FILE_SIZE


async def upload_documents(files: list[UploadFile], current_user: User, db: Session) -> dict:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one file is required")

    if len(files) > 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 10 files allowed")

    ensure_upload_directory()

    documents = []
    saved_files = []

    try:
        for file in files:
            content = await file.read(MAX_FILE_SIZE + 1)

            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"{file.filename} exceeds maximum file size")

            extension = validate_file(file.filename or "", file.content_type or "", content)
            stored_filename = generate_unique_filename(extension)
            file_path = get_storage_path(stored_filename)

            with open(file_path, "wb") as f:
                f.write(content)

            saved_files.append(file_path)

            document = Document(original_filename=Path(file.filename).name, stored_filename=stored_filename, file_path=str(file_path), content_type=file.content_type, file_size=len(content), file_extension=extension, owner_id=current_user.id)

            db.add(document)
            documents.append(document)

        db.commit()

        for document in documents:
            db.refresh(document)

        return {
            "message": "Documents uploaded successfully",
            "total_uploaded": len(documents),
            "documents": [DocumentResponse.model_validate(doc) for doc in documents]
        }

    except Exception:
        db.rollback()

        for file_path in saved_files:
            Path(file_path).unlink(missing_ok=True)

        raise

    finally:
        for file in files:
            await file.close()


def list_documents(db: Session, current_user: User, page: int, page_size: int, file_type: str | None, sort_by: str, sort_order: str) -> dict:
    current_roles = set(get_user_role_names(db, current_user.id))

    if current_roles.intersection({"admin", "manager"}):
        query = db.query(Document)
    else:
        shared_document_ids = db.query(document_shares.c.document_id).filter(
            document_shares.c.user_id == current_user.id
        )
        query = db.query(Document).filter(
            or_(Document.owner_id == current_user.id, Document.id.in_(shared_document_ids))
        )

    if file_type:
        extension = file_type.lower()
        if not extension.startswith("."):
            extension = f".{extension}"
        query = query.filter(Document.file_extension == extension)

    total = query.count()

    sort_columns = {
        "created_at": Document.created_at,
        "filename": Document.original_filename,
        "file_size": Document.file_size
    }

    column = sort_columns[sort_by]

    query = query.order_by(asc(column) if sort_order == "asc" else desc(column))

    documents = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "documents": documents
    }


def get_accessible_document(document_id: int, current_user: User, db: Session) -> Document:
    current_roles = set(get_user_role_names(db, current_user.id))
    query = db.query(Document).filter(Document.id == document_id)

    if not current_roles.intersection({"admin", "manager"}):
        shared_document = db.query(document_shares.c.document_id).filter(
            document_shares.c.document_id == document_id,
            document_shares.c.user_id == current_user.id,
        )
        query = query.filter(
            or_(Document.owner_id == current_user.id, Document.id.in_(shared_document))
        )

    document = query.first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return document


def get_document_for_download(document_id: int, current_user: User, db: Session) -> Document:
    document = get_accessible_document(document_id, current_user, db)

    path = get_storage_path(document.stored_filename)

    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")

    return document


def delete_document(document_id: int, current_user: User, db: Session) -> dict:
    current_roles = set(get_user_role_names(db, current_user.id))
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document or (
        document.owner_id != current_user.id
        and not current_roles.intersection({"admin", "manager"})
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    path = get_storage_path(document.stored_filename)

    db.execute(document_shares.delete().where(document_shares.c.document_id == document_id))
    db.delete(document)
    db.commit()

    path.unlink(missing_ok=True)

    return {
        "message": "Document deleted successfully",
        "document_id": document_id
    }


def share_document(db: Session, document_id: int, target_user_id: int, current_user: User) -> dict:
    current_roles = set(get_user_role_names(db, current_user.id))
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.owner_id != current_user.id and not current_roles.intersection({"admin", "manager"}):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only share documents you own")
    if not db.get(User, target_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if db.query(document_shares).filter_by(document_id=document_id, user_id=target_user_id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document is already shared with this user")

    try:
        db.execute(
            document_shares.insert().values(
                document_id=document_id,
                user_id=target_user_id,
                shared_by=current_user.id,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document is already shared with this user")
    return {"message": "Document shared successfully", "document_id": document_id, "user_id": target_user_id}


def revoke_document_share(db: Session, document_id: int, target_user_id: int, current_user: User) -> dict:
    current_roles = set(get_user_role_names(db, current_user.id))
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.owner_id != current_user.id and not current_roles.intersection({"admin", "manager"}):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage shares for documents you own")

    result = db.execute(
        document_shares.delete().where(
            document_shares.c.document_id == document_id,
            document_shares.c.user_id == target_user_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document share not found")

    db.commit()
    return {"message": "Document share revoked", "document_id": document_id, "user_id": target_user_id}