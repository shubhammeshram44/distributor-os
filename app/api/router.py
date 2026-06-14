from fastapi import APIRouter
from app.api.v1.whatsapp import router as whatsapp_router
from app.api.v1.ingestion import router as ingestion_router
from app.api.v1.mocks import router as mocks_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.products import router as products_router
from app.api.v1.orders import router as orders_router
from app.api.v1.customers import router as customers_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.shipments import router as shipments_router

api_router = APIRouter()
api_router.include_router(whatsapp_router)
api_router.include_router(ingestion_router)
api_router.include_router(mocks_router)
api_router.include_router(dashboard_router)
api_router.include_router(products_router)
api_router.include_router(orders_router)
api_router.include_router(customers_router)
api_router.include_router(analytics_router)
api_router.include_router(shipments_router)
