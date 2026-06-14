"""
VintedSpy — API FastAPI
Lance avec : uvicorn api:app --reload --port 8000
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json, sys
sys.path.insert(0, str(Path(__file__).parent))

app = FastAPI(title="VintedSpy API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    from database import get_conn
    return get_conn()

@app.get("/")
def root():
    return {"status": "ok", "app": "VintedSpy API"}

@app.get("/opportunites")
def opportunites(limit: int = Query(20, ge=1, le=100)):
    """Retourne les meilleures opportunités scorées."""
    from database import get_opportunites
    return get_opportunites(limit)

@app.get("/stats")
def stats():
    """Stats globales de la base."""
    from database import stats_db, get_conn
    s = stats_db()
    conn = get_conn()

    # Prix médians par niche
    niches = conn.execute("""
        SELECT marque, COUNT(*) as nb, AVG(prix) as prix_moy, MIN(prix) as prix_min, MAX(prix) as prix_max
        FROM prix_history
        GROUP BY marque
        ORDER BY nb DESC
    """).fetchall()
    conn.close()

    return {
        **s,
        "niches": [dict(n) for n in niches]
    }

@app.get("/annonces")
def annonces(
    marque: str = Query(None),
    prix_max: float = Query(None),
    score_min: int = Query(50),
    limit: int = Query(20)
):
    """Annonces filtrées avec scores."""
    from database import get_opportunites, get_conn
    opps = get_opportunites(100)

    if marque:
        opps = [o for o in opps if marque.lower() in (o.get("marque") or "").lower()]
    if prix_max:
        opps = [o for o in opps if o["prix"] <= prix_max]
    opps = [o for o in opps if o["score"] >= score_min]

    return opps[:limit]

@app.get("/median/{marque}/{taille}")
def median(marque: str, taille: str):
    """Prix médian pour une référence donnée."""
    from database import get_median_prix
    m = get_median_prix(marque, taille)
    return {"marque": marque, "taille": taille, "median": m}
