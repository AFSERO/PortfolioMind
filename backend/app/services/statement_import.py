import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.liability import Liability, LiabilityType
from app.models.liability_statement import LiabilityStatement
from app.schemas.liability_statement import StatementPdfPreflightResponse


PDF_CONTENT_TYPE = "application/pdf"
PDF_SIGNATURE = b"%PDF-"
READ_CHUNK_BYTES = 64 * 1024


class StatementPreflightError(ValueError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


async def preflight_statement_pdf(
    db: AsyncSession,
    *,
    liability_id: uuid.UUID,
    user_id: uuid.UUID,
    upload: UploadFile,
) -> StatementPdfPreflightResponse | None:
    liability = (
        await db.execute(
            select(Liability).where(
                Liability.id == liability_id,
                Liability.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if liability is None:
        return None
    if liability.liability_type != LiabilityType.CREDIT_CARD:
        raise StatementPreflightError(
            "liability_not_credit_card",
            "Statement PDFs can only be checked for credit-card liabilities",
            400,
        )

    raw_filename = (upload.filename or "").strip()
    # Normalize both POSIX and Windows client-side path separators without ever
    # resolving or touching a server filesystem path.
    filename = raw_filename.replace("\\", "/").rsplit("/", 1)[-1]
    content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if (
        not filename
        or Path(filename).suffix.lower() != ".pdf"
        or content_type != PDF_CONTENT_TYPE
    ):
        raise StatementPreflightError(
            "invalid_file_type",
            "Select a PDF file",
            415,
        )

    digest = hashlib.sha256()
    header = bytearray()
    size_bytes = 0

    while chunk := await upload.read(READ_CHUNK_BYTES):
        size_bytes += len(chunk)
        if size_bytes > settings.STATEMENT_PDF_MAX_BYTES:
            raise StatementPreflightError(
                "file_too_large",
                f"PDF exceeds the {settings.STATEMENT_PDF_MAX_BYTES} byte limit",
                413,
            )
        if len(header) < len(PDF_SIGNATURE):
            header.extend(chunk[: len(PDF_SIGNATURE) - len(header)])
        digest.update(chunk)

    if bytes(header) != PDF_SIGNATURE:
        raise StatementPreflightError(
            "invalid_pdf",
            "The file does not have a valid PDF signature",
            422,
        )

    sha256 = digest.hexdigest()
    matched_statement_id = (
        await db.execute(
            select(LiabilityStatement.id)
            .where(
                LiabilityStatement.user_id == user_id,
                LiabilityStatement.source_file_hash == sha256,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    is_duplicate = matched_statement_id is not None

    return StatementPdfPreflightResponse(
        filename=filename,
        size_bytes=size_bytes,
        sha256=sha256,
        is_pdf=True,
        is_duplicate=is_duplicate,
        matched_statement_id=matched_statement_id,
        status="duplicate_statement_file" if is_duplicate else "ready",
        analysis_available=False,
    )
