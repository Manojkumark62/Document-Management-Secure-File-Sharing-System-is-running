from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, func

from src.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    request_id = Column(String(32), nullable=False)
    method = Column(String(10), nullable=False)
    path = Column(String(2048), nullable=False)
    status_code = Column(Integer, nullable=False)
    client_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_events_actor_id", "actor_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )
