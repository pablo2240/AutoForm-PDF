import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Index, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class CommercialProfile(Base):
    __tablename__ = "commercial_profiles"
    __table_args__ = (
        Index("uq_commercial_profiles_email_lower", func.lower(Column("email")), unique=True),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_name = Column(String(100), nullable=False)   # e.g. "Kelly Delgado"
    nombre = Column(String(100), nullable=False)         # "Kelly Yohana"
    apellido = Column(String(100), nullable=False)       # "Delgado Macea"
    cargo = Column(String(100), nullable=False)          # "Asesor Comercial"
    email = Column(String(150), nullable=False, unique=True) # "Kelly.Delgado@iaclatam.com"
    celular = Column(String(50), nullable=False)         # "301 4750760"
    tipo_documento = Column(String(20), default="C.C")
    documento_identidad = Column(String(50), nullable=True) # Sensitive - excluded from public DTOs
    ciudad = Column(String(100), nullable=True)
    role = Column(String(30), default="commercial", nullable=False) # "admin" or "commercial"
    password_hash = Column(String(200), nullable=True)
    needs_password_hash_sync = Column(Boolean, default=False, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False) # Soft-delete flag
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_modified_by_ip = Column(String(45), nullable=True)

    def to_public_dict(self):
        """Returns non-sensitive fields for the public selector UI."""
        clean_cargo = self.cargo
        if clean_cargo and "lider comercial" in clean_cargo.lower():
            clean_cargo = "Asesor Comercial"
        return {
            "id": self.id,
            "profile_name": self.profile_name,
            "nombre": self.nombre,
            "apellido": self.apellido,
            "cargo": clean_cargo,
            "email": self.email,
            "celular": self.celular,
            "ciudad": self.ciudad or "",
            "role": self.role or "commercial",
            "is_active": self.is_active
        }

    def to_admin_dict(self):
        """Returns full fields for authorized administrative sessions."""
        return {
            "id": self.id,
            "profile_name": self.profile_name,
            "nombre": self.nombre,
            "apellido": self.apellido,
            "cargo": self.cargo,
            "email": self.email,
            "celular": self.celular,
            "ciudad": self.ciudad or "",
            "tipo_documento": self.tipo_documento or "C.C",
            "documento_identidad": self.documento_identidad or "",
            "role": self.role or "commercial",
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_modified_by_ip": self.last_modified_by_ip
        }


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index("ix_password_reset_tokens_token_hash", "token_hash", unique=True),
        Index("ix_password_reset_tokens_user_id", "user_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    request_ip = Column(String(45), nullable=True)


class UserDocument(Base):
    __tablename__ = "user_documents"
    __table_args__ = (
        Index("idx_user_documents_user_active", "user_id", "is_active"),
        Index("idx_user_documents_company", "company_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    template_code = Column(String(100), nullable=True)
    filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    size_kb = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "user_id": self.user_id,
            "template_code": self.template_code,
            "filename": self.filename,
            "storage_path": self.storage_path,
            "size_kb": self.size_kb,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


