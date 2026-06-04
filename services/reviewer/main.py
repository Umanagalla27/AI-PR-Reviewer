from fastapi import FastAPI
from starlette_prometheus import metrics, PrometheusMiddleware
from shared.observability import RequestIdMiddleware
from services.reviewer.routes import router

app = FastAPI(title="Reviewer Service")

app.add_middleware(RequestIdMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "reviewer", "db": True}


app.include_router(router)
