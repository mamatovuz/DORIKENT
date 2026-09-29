from .employee import router as employee_router
from .test_taking import router as test_taking_router
from .admin import router as admin_router
from .recruitment import router as recruitment_router

# Router tartibi muhim: admin va employee alohida, test_taking callbacklar uchun.
# recruitment — 2-bot nomzodlari uchun (rbegin: callbacklari).
__all__ = [
    "employee_router", "test_taking_router", "admin_router", "recruitment_router",
]
