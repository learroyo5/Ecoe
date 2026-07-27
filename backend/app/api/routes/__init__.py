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
from app.api.routes.users import router as users_router
from app.api.routes.invitations import router as invitations_router
from app.api.routes.contingency import router as contingency_router
from app.api.routes.kiosk import router as kiosk_router
from app.api.routes.grading import router as grading_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(ecoe_router)
router.include_router(students_router)
router.include_router(staff_router)
router.include_router(evaluator_router)
router.include_router(student_access_router)
router.include_router(stations_router)
router.include_router(operational_router)
router.include_router(users_router)
router.include_router(invitations_router)
router.include_router(contingency_router)
router.include_router(kiosk_router)
router.include_router(grading_router)
