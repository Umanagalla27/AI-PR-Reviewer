"""
Gateway Service — entry point.

Creates the FastAPI application, adds middleware, and includes
the route handlers from routes.py.
"""

from fastapi import FastAPI
from starlette_prometheus import metrics, PrometheusMiddleware
from shared.observability import RequestIdMiddleware

from services.gateway.routes import router

app = FastAPI(title="Gateway Service")

# Middleware
app.add_middleware(RequestIdMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

# Health endpoint (kept here since it's app-level, not webhook logic)
@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}

# Include webhook routes from routes.py
app.include_router(router)
