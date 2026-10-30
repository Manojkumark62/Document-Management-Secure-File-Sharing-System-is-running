from sqlalchemy.orm import Session

def save_document_record(db: Session, document):
    try:
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        raise