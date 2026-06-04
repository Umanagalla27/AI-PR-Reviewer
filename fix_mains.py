services = ["webhook", "orchestrator", "reviewer", "learner"]
for svc in services:
    main_path = f"services/{svc}/main.py"
    title = svc.capitalize() + " Service"

    new_content = f'''from fastapi import FastAPI
from starlette_prometheus import metrics, PrometheusMiddleware
from shared.observability import RequestIdMiddleware
from services.{svc}.routes import router

app = FastAPI(title="{title}")

app.add_middleware(RequestIdMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

@app.get("/health")
async def health():
    return {{"status": "ok", "service": "{svc}", "db": True}}

app.include_router(router)
'''
    with open(main_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Rewrote {main_path}")
