from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pymongo.errors import PyMongoError
from starlette.responses import Response

from supplyguard.core.config import get_settings
from supplyguard.domain.models import AskRequest, AskResponse, FeedbackRequest
from supplyguard.infrastructure.vector import VectorStoreError

router = APIRouter()


def actor(x_api_key: str = Header(default="")) -> str:
    """Authenticate the API key and return its allowlisted application role."""
    role = get_settings().key_roles().get(x_api_key)
    if not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
    return role


@router.post("/v1/ask", response_model=AskResponse)
async def ask(payload: AskRequest, request: Request, role: str = Depends(actor)):
    """Route a validated question through the central assistant orchestrator."""
    return await request.app.state.orchestrator.ask(payload, role)


@router.post("/v1/feedback", status_code=201)
async def feedback(payload: FeedbackRequest, request: Request, role: str = Depends(actor)):
    """Upsert one explicit quality signal without modifying the model or prompt."""
    doc = {**payload.model_dump(), "actor": role}
    result = await request.app.state.mongo.db.feedback.update_one(
        {"request_id": payload.request_id}, {"$set": doc}, upsert=True)
    return {"stored": bool(result.acknowledged), "reinforcement_learning": False,
            "note": "Explicit evaluation signal only; no policy/model update occurs automatically."}


@router.get("/v1/feedback/{request_id}")
async def feedback_status(request_id: str, request: Request, role: str = Depends(actor)):
    """Return persisted feedback state so clients do not rely on transient UI memory."""
    if len(request_id) > 128:
        raise HTTPException(status_code=422, detail="invalid request ID")
    doc = await request.app.state.mongo.db.feedback.find_one(
        {"request_id": request_id}, {"_id": 0, "helpful": 1, "reason": 1}
    )
    if not doc:
        return {"submitted": False}
    return {"submitted": True, "helpful": doc["helpful"], "reason": doc.get("reason")}


@router.get("/health/live")
async def live():
    """Report process liveness without checking slower downstream dependencies."""
    return {"status": "alive"}


@router.get("/health/ready")
async def ready(request: Request):
    """Report whether every dependency required to answer questions is reachable."""
    dependencies = {"mongodb": await request.app.state.mongo.ready(),
                    "qdrant": await request.app.state.vectors.ready(),
                    "ollama": await request.app.state.ollama.ready(),
                    "mcp": await request.app.state.mcp.ready()}
    if not all(dependencies.values()):
        raise HTTPException(503, {"status": "degraded", "dependencies": dependencies})
    return {"status": "ready", "dependencies": dependencies}


@router.get("/metrics", include_in_schema=False)
async def metrics():
    """Expose Prometheus metrics for infrastructure monitoring."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/v1/storage/stats")
async def storage_stats(request: Request, role: str = Depends(actor)):
    """Expose authenticated MongoDB and Qdrant persistence counts for reviewers."""
    db = request.app.state.mongo.db
    try:
        mongo = {
            "chunks": await db.chunks.count_documents({}),
            "structured_records": await db.records.count_documents({}),
            "ingestion_runs": await db.ingestion_runs.count_documents({}),
            "audit_events": await db.audit_events.count_documents({}),
            "feedback": await db.feedback.count_documents({}),
            "conversation_turns": await db.conversation_turns.count_documents({}),
        }
        qdrant = await request.app.state.vectors.stats()
    except (PyMongoError, VectorStoreError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "storage unavailable", "error_type": type(exc).__name__},
        ) from exc
    return {"status": "available", "requested_by_role": role,
            "mongodb": mongo, "qdrant": qdrant}
