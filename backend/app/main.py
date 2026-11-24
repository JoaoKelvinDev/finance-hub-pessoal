from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, install_request_id

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title="Finance Hub Pessoal", version="0.1.0", docs_url="/docs", redoc_url=None)
install_request_id(app)
install_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.include_router(api_router)


@app.get("/health", tags=["Sessão"])
def health():
    return {"status": "ok"}
