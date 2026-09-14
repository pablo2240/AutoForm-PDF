import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class CommercialProfile(Base):
    __tablename__ = "commercial_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_name = Column(String(100), nullable=False)   # e.g. "Kelly Delgado"
    nombre = Column(String(100), nullable=False)         # "Kelly Yohana"
    apellido = Column(String(100), nullable=False)       # "Delgado Macea"
    cargo = Column(String(100), nullable=False)          # "Asesor Comercial"
    email = Column(String(150), nullable=False, unique=True) # "Kelly.Delgado@iaclatam.com"
    celular = Column(String(50), nullable=False)         # "301 4750760"
    tipo_documento = Column(String(20), default="C.C")
    documento_identidad = Column(String(50), nullable=True) # Sensitive - excluded from public DTOs
    role = Column(String(30), default="commercial", nullable=False) # "admin" or "commercial"
    password_hash = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False) # Soft-delete flag
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_modified_by_ip = Column(String(45), nullable=True)

    def to_public_dict(self):
        """Returns non-sensitive fields for the public selector UI."""
        return {
            "id": self.id,
            "profile_name": self.profile_name,
            "nombre": self.nombre,
            "apellido": self.apellido,
            "cargo": self.cargo,
            "email": self.email,
            "celular": self.celular,
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
            "tipo_documento": self.tipo_documento or "C.C",
            "documento_identidad": self.documento_identidad or "",
            "role": self.role or "commercial",
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_modified_by_ip": self.last_modified_by_ip
        }
