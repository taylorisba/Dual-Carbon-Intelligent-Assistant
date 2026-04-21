from fastapi import APIRouter

from app.api.v1.endpoints import chat, documents, report, sources, system


api_router = APIRouter()
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(report.router, prefix="/report", tags=["report"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
