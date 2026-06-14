"""
VintedSpy — API FastAPI
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

app = FastAPI(title="VintedSpy API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "app": "VintedSpy API"}

@app.get("/opportunites")
def opportunites(limit: int = Query(20, ge=1, le=100)):
    try:
        from database import get_opportunites
        return get_opportunites(limit)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/stats")
def stats():
    try:
        from database import stats_db
        return stats_db()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/annonces")
def annonces(
    marque: str = Query(None),
    prix_max: float = Query(None),
    score_min: int = Query(30),
    limit: int = Query(20)
):
    try:
        from database import get_opportunites
        opps = get_opportunites(100)
        if marque:
            opps = [o for o in opps if marque.lower() in (o.get("marque") or "").lower()]
        if prix_max:
            opps = [o for o in opps if o["prix"] <= prix_max]
        opps = [o for o in opps if o.get("score", 0) >= score_min]
        return opps[:limit]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/ping")
def ping():
    try:
        from database import stats_db
        s = stats_db()
        return {"status": "ok", "annonces": s.get("annonces", 0), "prix_history": s.get("prix_history", 0)}
    except Exception as e:
        return {"status": "db_error", "error": str(e)}
