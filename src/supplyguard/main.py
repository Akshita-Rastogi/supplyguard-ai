from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from supplyguard.api.routes import router
from supplyguard.core.config import get_settings
from supplyguard.core.logging import configure_logging, log
from supplyguard.core.middleware import RequestContextMiddleware
from supplyguard.infrastructure.mcp_client import MCPGateway
from supplyguard.infrastructure.mongo import Mongo
from supplyguard.infrastructure.ollama import OllamaClient
from supplyguard.infrastructure.vector import VectorStore
from supplyguard.services.orchestrator import Orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared dependency clients on startup and close them on shutdown."""
    configure_logging()
    settings = get_settings()
    app.state.mongo = Mongo(settings)
    app.state.ollama = OllamaClient(settings.ollama_base_url, settings.ollama_chat_model,
                                    settings.ollama_embed_model)
    app.state.vectors = VectorStore(settings.qdrant_url, settings.qdrant_collection)
    app.state.mcp = MCPGateway(settings.mcp_server_url)
    if await app.state.mongo.ready():
        await app.state.mongo.ensure_indexes()
    app.state.orchestrator = Orchestrator(app.state.mongo.db, app.state.vectors,
                                          app.state.ollama, app.state.mcp, settings)
    log.info("service_started", environment=settings.app_env)
    yield
    await app.state.ollama.close()
    await app.state.vectors.close()
    await app.state.mongo.client.close()


app = FastAPI(title="SupplyGuard AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.include_router(router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """Log unexpected failures internally while returning a non-sensitive error."""
    log.exception("unhandled_error", path=request.url.path, error_type=type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})
