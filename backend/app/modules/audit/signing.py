"""Tenant Ed25519 key management and canonical signed audit exports."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import uuid7
from app.core.settings import get_settings
from app.modules.audit.models import TenantAuditKey


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def create_tenant_key(db: Session, tenant_id: uuid.UUID, *, version: int = 1) -> TenantAuditKey:
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public_raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    nonce = os.urandom(12)
    encrypted = AESGCM(_master_key()).encrypt(nonce, private_raw, str(tenant_id).encode())
    key = TenantAuditKey(
        id=uuid7(),
        tenant_id=tenant_id,
        version=version,
        public_key=public_raw,
        encrypted_private_key=encrypted,
        nonce=nonce,
        fingerprint=hashlib.sha256(public_raw).hexdigest(),
        active=True,
    )
    db.add(key)
    db.flush()
    return key


def get_or_create_active_key(db: Session, tenant_id: uuid.UUID) -> TenantAuditKey:
    key = (
        db.execute(
            select(TenantAuditKey)
            .where(
                TenantAuditKey.tenant_id == tenant_id,
                TenantAuditKey.active.is_(True),
            )
            .order_by(TenantAuditKey.version.desc())
        )
        .scalars()
        .first()
    )
    return key or create_tenant_key(db, tenant_id)


def sign_document(db: Session, tenant_id: uuid.UUID, document: dict[str, Any]) -> dict[str, str]:
    key = get_or_create_active_key(db, tenant_id)
    private_raw = AESGCM(_master_key()).decrypt(
        key.nonce, key.encrypted_private_key, str(tenant_id).encode()
    )
    signature = Ed25519PrivateKey.from_private_bytes(private_raw).sign(canonical_json(document))
    return {
        "algorithm": "Ed25519",
        "canonicalization": "JCS-compatible",
        "key_id": str(key.id),
        "key_version": str(key.version),
        "key_fingerprint": key.fingerprint,
        "signature": base64.b64encode(signature).decode(),
    }


def verify_document(public_key: bytes, document: dict[str, Any], signature_b64: str) -> None:
    Ed25519PublicKey.from_public_bytes(public_key).verify(
        base64.b64decode(signature_b64), canonical_json(document)
    )


def _master_key() -> bytes:
    raw = get_settings().audit_master_key
    if not raw:
        # Demo-safe fallback keeps bootstrap idempotent. Production deployments
        # must set a separate KEK; the default JWT secret is already rejected
        # operationally by deployment configuration.
        return hashlib.sha256(get_settings().jwt_secret.encode()).digest()
    try:
        decoded = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise RuntimeError("VAIC_AUDIT_MASTER_KEY must be valid base64") from exc
    if len(decoded) != 32:
        raise RuntimeError("VAIC_AUDIT_MASTER_KEY must decode to exactly 32 bytes")
    return decoded
