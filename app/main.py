from fastapi import FastAPI

from app.api.routes import router
from app.config import settings
from app.logging_config import configure_logging

configure_logging(settings.log_level)

app = FastAPI(title="AI Incident Resolution Agent", version="1.0.0")
app.include_router(router)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}
