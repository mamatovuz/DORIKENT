"""FastAPI ilovasi va uni Telegram bot bilan bir vaqtda ishga tushirish."""
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

import config
from .routes import router

log = logging.getLogger("api.app")


def create_app() -> FastAPI:
    app = FastAPI(
        title="DoriKent Test Bot API",
        version="1.0.0",
        description="Ish topish boti (2-bot) integratsiyasi uchun REST API.",
    )
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request, exc: RequestValidationError):
        # Yagona, izchil xato formati (secret hech qachon aks etmaydi).
        return JSONResponse(
            status_code=422,
            content={"success": False, "error": "validation_error",
                     "details": exc.errors()},
        )

    return app


async def run_api() -> None:
    """API serverni joriy asyncio loop ichida ishga tushiradi (bot bilan birga).

    uvicorn signal handlerlari o'chirilgan — chunki bot allaqachon
    asosiy loopni boshqaradi (aks holda Windows/Unix da konflikt bo'lishi mumkin).
    """
    import uvicorn

    uv_config = uvicorn.Config(
        create_app(),
        host=config.API_HOST,
        port=config.API_PORT,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(uv_config)
    server.install_signal_handlers = lambda: None  # loop bot ixtiyorida
    log.info("API server ishga tushmoqda: http://%s:%s", config.API_HOST, config.API_PORT)
    await server.serve()
