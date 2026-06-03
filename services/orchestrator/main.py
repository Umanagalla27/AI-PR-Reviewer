from fastapi import FastAPI
from starlette_prometheus import metrics, PrometheusMiddleware
from shared.observability import RequestIdMiddleware
from services.orchestrator.routes import router

app = FastAPI(title="Orchestrator Service")

app.add_middleware(RequestIdMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "orchestrator", "db": True}

app.include_router(router)
