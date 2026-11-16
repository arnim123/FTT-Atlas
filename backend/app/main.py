from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.middleware import AuditMiddleware, ExternalGateMiddleware, OAuthCorsMiddleware
from app.api.oauth import public_router as oauth_public_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.csrf import CSRFMiddleware
from app.core.redact import install_redaction
from app.ingestion import register_ingestion_handlers, start_ingestion_worker, stop_ingestion_worker
from app.integrations.drive_sync import register_drive_sync_handlers, start_reconcile_scheduler, stop_reconcile_scheduler
from app.mcp.server import install_session_manager, mcp_app
from app.services.oauth import register_oauth_handlers, start_oauth_cleanup, stop_oauth_cleanup
from app.services.tokens import register_token_handlers


@asynccontextmanager
async def _lifespan(application: FastAPI):
    register_drive_sync_handlers()
    register_ingestion_handlers()
    register_token_handlers()
    register_oauth_handlers()
    start_reconcile_scheduler()
    start_ingestion_worker()
    start_oauth_cleanup()
    async with install_session_manager().run():
        yield
    stop_oauth_cleanup()
    stop_ingestion_worker()
    stop_reconcile_scheduler()


def create_app() -> FastAPI:
    install_redaction()
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=_lifespan,
        openapi_tags=[
            {
                "name": "folders",
                "description": "Folder tree, rename, move, soft delete, and grants. A folder the caller cannot view returns 404.",
            },
            {
                "name": "documents",
                "description": (
                    "Documents, uploaded files, Google Docs, versions, grants, and extracted text. Every document includes my_access and web_url. "
                    "GET /content returns document text labeled as content, in pages. A document the caller cannot view returns 404. "
                    "Reads require docs:read. Changes require docs:write."
                ),
            },
            {
                "name": "search",
                "description": (
                    "Permission-filtered full-text and trigram search. Facets, snippets, and suggestions use the same "
                    "accessible-document rule as the document list. Reads require docs:read."
                ),
            },
            {
                "name": "dashboard",
                "description": (
                    "Workspace counts and recent activity. Every document figure counts only documents the caller can view. "
                    "Reads require docs:read."
                ),
            },
            {
                "name": "admin",
                "description": "Operator actions. Reindex queues extraction for one document. Admins only, and docs:write is required.",
            },
        ],
    )
    application.add_middleware(CSRFMiddleware)
    application.add_middleware(ExternalGateMiddleware)
    application.add_middleware(AuditMiddleware)
    application.add_middleware(OAuthCorsMiddleware)
    application.include_router(oauth_public_router)
    application.include_router(api_router, prefix="/api/v1")
    # Mounted at / so the Streamable HTTP route stays /mcp and the OAuth metadata
    # route stays /.well-known/oauth-protected-resource/mcp. API routes are registered first.
    application.mount("/", mcp_app)
    return application


app = create_app()
