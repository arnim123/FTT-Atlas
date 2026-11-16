from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.agent import download_router as agent_download_router
from app.api.agent import openapi_router as agent_openapi_router
from app.api.agent import router as agent_router
from app.api.audit import admin_router as audit_admin_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.documents import router as documents_router
from app.api.folders import router as folders_router
from app.api.health import router as health_router
from app.api.oauth import admin_router as oauth_admin_router
from app.api.oauth import router as oauth_router
from app.api.org_settings import read_router as org_settings_read_router
from app.api.org_settings import router as org_settings_router
from app.api.search import router as search_router
from app.api.taxonomy import categories_router, departments_router, tags_router
from app.api.tokens import admin_router as token_admin_router
from app.api.tokens import router as tokens_router
from app.api.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(departments_router, prefix="/departments", tags=["departments"])
api_router.include_router(categories_router, prefix="/categories", tags=["categories"])
api_router.include_router(tags_router, prefix="/tags", tags=["tags"])
api_router.include_router(folders_router, prefix="/folders", tags=["folders"])
api_router.include_router(documents_router, prefix="/documents", tags=["documents"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(tokens_router, prefix="/tokens", tags=["tokens"])
api_router.include_router(token_admin_router, prefix="/admin", tags=["tokens"])
api_router.include_router(org_settings_read_router, tags=["admin"])
api_router.include_router(org_settings_router, prefix="/admin", tags=["admin"])
api_router.include_router(oauth_router, prefix="/oauth", tags=["oauth"])
api_router.include_router(oauth_admin_router, prefix="/admin", tags=["oauth"])
api_router.include_router(audit_router, prefix="/me", tags=["audit"])
api_router.include_router(audit_admin_router, prefix="/admin", tags=["audit"])
api_router.include_router(agent_router, prefix="/agent", tags=["agent"])
api_router.include_router(agent_download_router, prefix="/agent", tags=["agent"])
api_router.include_router(agent_openapi_router, prefix="/agent", tags=["agent"])
