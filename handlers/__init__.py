from .employee import router as employee_router
from .test_taking import router as test_taking_router
from .admin import router as admin_router

# Router tartibi muhim: admin va employee alohida, test_taking callbacklar uchun.
__all__ = ["employee_router", "test_taking_router", "admin_router"]
