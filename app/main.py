from fastapi import FastAPI

from app.api.graph import router as graph_router
from app.api.search import router as search_router
from app.api.suitability import router as suitability_router
from app.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(search_router)
app.include_router(graph_router)
app.include_router(suitability_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}
