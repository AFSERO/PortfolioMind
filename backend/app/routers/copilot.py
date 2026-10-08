import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.copilot import CopilotMessage
from app.models.user import User
from app.schemas.copilot import (
    ActionProposalCancelRequest,
    ActionProposalConfirmRequest,
    ActionProposalResponse,
    CopilotConversationCreateRequest,
    CopilotConversationResponse,
    CopilotMessageCreateRequest,
    CopilotMessageResponse,
    CopilotResponseType,
    CopilotStructuredResponse,
)
from app.schemas.portfolio_import import (
    ImportItemResolutionRequest,
    ImportSourceType,
    PortfolioImportBatchResponse,
)
from app.services.copilot import (
    CopilotProposalService,
    CopilotService,
    CopilotWriteExecutor,
)
from app.services.copilot.import_parsers import ImagePortfolioParser
from app.services.copilot.import_service import PortfolioImportService


router = APIRouter()


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: CopilotConversationCreateRequest = CopilotConversationCreateRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new conversation session for the current user."""
    conv = await CopilotService.create_conversation(
        db=db,
        user_id=current_user.id,
        title=body.title,
    )
    return {
        "status": "success",
        "data": CopilotConversationResponse.model_validate(conv).model_dump(mode="json"),
    }


@router.get("/conversations")
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all conversations owned by the current user."""
    convs = await CopilotService.list_conversations(db=db, user_id=current_user.id)
    return {
        "status": "success",
        "data": [
            CopilotConversationResponse.model_validate(c).model_dump(mode="json")
            for c in convs
        ],
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve a conversation and its messages. Verifies user ownership."""
    conv = await CopilotService.get_conversation(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return {
        "status": "success",
        "data": CopilotConversationResponse.model_validate(conv).model_dump(mode="json"),
    }


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a conversation if owned by the current user."""
    deleted = await CopilotService.delete_conversation(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    body: CopilotMessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Post a user message, run intent detection and context selection, and return assistant response with provenance."""
    assistant_msg, structured_resp = await CopilotService.send_message(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        content=body.content,
        page_context=body.page_context,
    )
    return {
        "status": "success",
        "data": {
            "message": CopilotMessageResponse.model_validate(assistant_msg).model_dump(mode="json"),
            "structured_response": structured_resp.model_dump(mode="json"),
            "context_used": [
                item.model_dump(mode="json") for item in structured_resp.context_used
            ],
        },
    }


@router.get("/proposals/{proposal_id}")
async def get_proposal(
    proposal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve details for a specific action proposal."""
    proposal = await CopilotProposalService.get_proposal(
        db=db, user_id=current_user.id, proposal_id=proposal_id
    )
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action proposal not found",
        )
    return {
        "status": "success",
        "data": ActionProposalResponse.model_validate(proposal).model_dump(mode="json"),
    }


@router.post("/proposals/{proposal_id}/confirm")
async def confirm_proposal(
    proposal_id: uuid.UUID,
    body: ActionProposalConfirmRequest = ActionProposalConfirmRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Confirm and execute a staged action proposal via the narrow write engine."""
    result = await CopilotWriteExecutor.execute_proposal(
        db=db,
        user_id=current_user.id,
        proposal_id=proposal_id,
        idempotency_key=body.idempotency_key,
        confirmation_text=body.confirmation_text,
    )
    proposal = await CopilotProposalService.get_proposal(
        db=db, user_id=current_user.id, proposal_id=proposal_id
    )
    return {
        "status": "success",
        "data": {
            "proposal": (
                ActionProposalResponse.model_validate(proposal).model_dump(mode="json")
                if proposal
                else None
            ),
            "execution_result": result,
        },
    }


@router.post("/proposals/{proposal_id}/cancel")
async def cancel_proposal(
    proposal_id: uuid.UUID,
    body: ActionProposalCancelRequest = ActionProposalCancelRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel a pending action proposal."""
    cancelled = await CopilotProposalService.cancel_proposal(
        db=db,
        user_id=current_user.id,
        proposal_id=proposal_id,
        reason=body.reason,
    )
    return {
        "status": "success",
        "data": ActionProposalResponse.model_validate(cancelled).model_dump(mode="json"),
    }


# ---------------------------------------------------------------------------
# Portfolio Import Endpoints (Phase 3)
# ---------------------------------------------------------------------------


@router.post("/conversations/{conversation_id}/import/upload")
async def upload_import_file(
    conversation_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a CSV or Screenshot image to create an import batch draft in this conversation."""
    conversation = await CopilotService.get_conversation(db, current_user.id, conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied.",
        )

    filename = (file.filename or "unknown").strip()
    contents = await file.read(10 * 1024 * 1024 + 1)
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(413, "Upload exceeds 10 MB.")
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yüklenen dosya boş.",
        )

    # Detect file type
    is_csv = filename.lower().endswith(".csv") or (file.content_type and "csv" in file.content_type.lower())
    is_image = any(filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")) or (
        file.content_type and "image" in file.content_type.lower()
    )

    if not is_csv and not is_image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Desteklenmeyen dosya formatı. Lütfen CSV veya görsel (PNG/JPEG/WEBP) yükleyin.",
        )

    # 1. Add user message into conversation
    user_msg = CopilotMessage(
        conversation_id=conversation_id,
        role="user",
        raw_content=f"Dosya yüklendi: {filename}",
    )
    db.add(user_msg)
    await db.flush()

    # 2. Process import
    if is_csv:
        try:
            csv_text = contents.decode("utf-8")
        except UnicodeDecodeError:
            csv_text = contents.decode("latin1", errors="replace")

        batch = await PortfolioImportService.process_import(
            db=db,
            user_id=current_user.id,
            conversation_id=conversation_id,
            source_type=ImportSourceType.CSV.value,
            raw_content=csv_text,
            source_reference=filename,
        )
    else:
        # Validate image bytes
        try:
            ImagePortfolioParser.validate_image_bytes(contents, file.content_type)
        except Exception as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

        raise HTTPException(501, "Screenshot extraction provider is not configured. Please use CSV or natural-language import.")

    batch_resp = PortfolioImportService.to_batch_response(batch)
    proposal_resp = None
    if batch.proposal:
        proposal_resp = ActionProposalResponse.model_validate(batch.proposal)

    answer = (
        f"'{filename}' dosyasından {len(batch.items)} varlık tespit edildi: "
        f"{batch_resp.ready_count} hazır, {batch_resp.needs_review_count} inceleme bekleyen, {batch_resp.ambiguous_count} belirsiz. "
        "Aşağıdaki önizleme kartından kalemleri inceleyebilirsiniz."
    )

    structured_resp = CopilotStructuredResponse(
        response_type=CopilotResponseType.PROPOSAL if batch.status == "READY_FOR_CONFIRMATION" else CopilotResponseType.NEEDS_INPUT,
        answer=answer,
        intent="PORTFOLIO_IMPORT",
        execution_mode="PROPOSE",
        proposal=proposal_resp,
        import_batch=batch_resp,
        context_used=[],
    )

    # 3. Add assistant message into conversation
    assistant_msg = CopilotMessage(
        conversation_id=conversation_id,
        role="assistant",
        raw_content=answer,
        intent="PORTFOLIO_IMPORT",
        structured_metadata=structured_resp.model_dump(mode="json"),
    )
    db.add(assistant_msg)
    await db.commit()

    return {
        "status": "success",
        "data": {
            "message": CopilotMessageResponse.model_validate(assistant_msg).model_dump(mode="json"),
            "response": structured_resp.model_dump(mode="json"),
            "batch": batch_resp.model_dump(mode="json"),
        },
    }


@router.get("/import/batches/{batch_id}")
async def get_import_batch(
    batch_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fetch details and current status of an import batch."""
    batch = await PortfolioImportService.get_batch(db, current_user.id, batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import batch not found or access denied.",
        )
    return {
        "status": "success",
        "data": PortfolioImportService.to_batch_response(batch).model_dump(mode="json"),
    }


@router.post("/import/batches/{batch_id}/items/{item_id}/resolve")
async def resolve_import_item(
    batch_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ImportItemResolutionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resolve ambiguity or supply missing data for an individual import item."""
    try:
        batch, item = await PortfolioImportService.resolve_item(
            db=db,
            user_id=current_user.id,
            batch_id=batch_id,
            item_id=item_id,
            resolution=body,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )
    return {
        "status": "success",
        "data": PortfolioImportService.to_batch_response(batch).model_dump(mode="json"),
    }




