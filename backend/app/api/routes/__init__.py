"""API routes — combines all domain routers into a single top-level router."""

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.ecoe import router as ecoe_router
from app.api.routes.students import router as students_router
from app.api.routes.staff import router as staff_router
from app.api.routes.evaluator import router as evaluator_router
from app.api.routes.student_access import router as student_access_router
from app.api.routes.stations import router as stations_router
from app.api.routes.operational import router as operational_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(ecoe_router)
router.include_router(students_router)
router.include_router(staff_router)
router.include_router(evaluator_router)
router.include_router(student_access_router)
router.include_router(stations_router)
router.include_router(operational_router)
