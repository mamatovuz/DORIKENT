"""DoriKent Test Bot — REST API (2-bot / Ish topish boti integratsiyasi).

Bu paket 1-bot ichida FastAPI asosidagi API serverni ta'minlaydi. 2-bot faqat
shu API orqali bog'lanadi — hech qachon 1-bot SQLite fayliga to'g'ridan-to'g'ri
ulanmaydi.
"""
from .app import create_app, run_api

__all__ = ["create_app", "run_api"]
