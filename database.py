"""
VintedSpy — Database
SQLite en local, PostgreSQL sur Railway (via DATABASE_URL).
"""
import os, statistics, logging
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("database")
DATABASE_URL = os.getenv("DATABASE_URL")  # Set par Railway automatiquement

# --- CONNEXION ---

def get_conn():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn, "pg"
    else:
        import sqlite3
        db_path = Path.home() / "Downloads" / "vintedspy.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"

def fetchall(cursor):
    rows = cursor.fetchall()
    if not rows:
        return []
    if hasattr(rows[0], 'keys'):
        return [dict(r) for r in rows]
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]

# --- INIT ---

def init_db():
    conn, mode = get_conn()
    cur = conn.cursor()
    ph = "%s" if mode == "pg" else "?"

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS annonces (
            id          {'BIGINT' if mode=='pg' else 'INTEGER'} PRIMARY KEY,
            titre       TEXT,
            marque      TEXT,
            taille      TEXT,
            prix        REAL,
            nb_favoris  INTEGER,
            url         TEXT,
            photo       TEXT,
            vendeur     TEXT,
            scraped_le  TEXT
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS prix_history (
            id          {'BIGSERIAL' if mode=='pg' else 'INTEGER PRIMARY KEY AUTOINCREMENT'},
            marque      TEXT,
            taille      TEXT,
            prix        REAL,
            scraped_le  TEXT
        )
    """ if mode == "sqlite" else f"""
        CREATE TABLE IF NOT EXISTS prix_history (
            id          BIGSERIAL PRIMARY KEY,
            marque      TEXT,
            taille      TEXT,
            prix        REAL,
            scraped_le  TEXT
        )
    """)
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_marque_taille ON prix_history(marque, taille)")
    except:
        pass
    conn.commit()
    conn.close()
    log.info(f"DB initialisée ({mode})")

# --- CRUD ---

def sauvegarder_annonces(annonces: list[dict]) -> int:
    conn, mode = get_conn()
    cur = conn.cursor()
    ph = "%s" if mode == "pg" else "?"
    nouvelles = 0

    for a in annonces:
        try:
            if mode == "pg":
                cur.execute(f"""
                    INSERT INTO annonces (id,titre,marque,taille,prix,nb_favoris,url,photo,vendeur,scraped_le)
                    VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                    ON CONFLICT (id) DO NOTHING
                """, (a["id"],a["titre"],a["marque"],a["taille"],a["prix"],
                      a["nb_favoris"],a["url"],a.get("photo",""),a.get("vendeur",""),
                      datetime.now().isoformat()))
                if cur.rowcount > 0:
                    nouvelles += 1
                    cur.execute(f"INSERT INTO prix_history (marque,taille,prix,scraped_le) VALUES ({ph},{ph},{ph},{ph})",
                        (a["marque"],a["taille"],a["prix"],datetime.now().isoformat()))
            else:
                cur.execute(f"""
                    INSERT OR IGNORE INTO annonces (id,titre,marque,taille,prix,nb_favoris,url,photo,vendeur,scraped_le)
                    VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                """, (a["id"],a["titre"],a["marque"],a["taille"],a["prix"],
                      a["nb_favoris"],a["url"],a.get("photo",""),a.get("vendeur",""),
                      datetime.now().isoformat()))
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    nouvelles += 1
                    cur.execute(f"INSERT INTO prix_history (marque,taille,prix,scraped_le) VALUES ({ph},{ph},{ph},{ph})",
                        (a["marque"],a["taille"],a["prix"],datetime.now().isoformat()))
        except Exception as e:
            log.error(f"Erreur insertion {a.get('id')}: {e}")

    conn.commit()
    conn.close()
    return nouvelles

def get_median_prix(marque: str, taille: str, jours: int = 90):
    conn, mode = get_conn()
    cur = conn.cursor()
    ph = "%s" if mode == "pg" else "?"
    since = (datetime.now() - timedelta(days=jours)).isoformat()
    cur.execute(f"""
        SELECT prix FROM prix_history
        WHERE marque = {ph} AND taille = {ph} AND scraped_le > {ph}
        ORDER BY scraped_le DESC LIMIT 200
    """, (marque, taille, since))
    rows = fetchall(cur)
    conn.close()
    if len(rows) < 3:
        return None
    return round(statistics.median([r["prix"] for r in rows]), 2)

def scorer_annonce(annonce: dict, prix_median) -> int:
    if not prix_median or annonce["prix"] <= 0:
        return 0
    ecart = (prix_median - annonce["prix"]) / prix_median
    score_ecart = min(ecart * 1.5, 1.0) * 40
    score_favs = min(annonce["nb_favoris"] / 10, 1.0) * 30
    marge = prix_median - annonce["prix"]
    score_marge = min(marge / 30, 1.0) * 30
    return min(int(score_ecart + score_favs + score_marge), 100)

def get_opportunites(limit: int = 20) -> list[dict]:
    conn, mode = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM annonces ORDER BY scraped_le DESC LIMIT 100")
    annonces = fetchall(cur)
    conn.close()

    resultats = []
    for a in annonces:
        median = get_median_prix(a["marque"], a["taille"])
        score = scorer_annonce(a, median)
        if score > 0:
            a["prix_median"] = median
            a["ecart_pct"] = round((median - a["prix"]) / median * 100) if median else 0
            a["marge_nette"] = round(median - a["prix"] - (a["prix"] * 0.05) - 0.70, 2) if median else 0
            a["score"] = score
            resultats.append(a)

    return sorted(resultats, key=lambda x: x["score"], reverse=True)[:limit]

def stats_db() -> dict:
    conn, mode = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as n FROM annonces")
    nb_a = fetchall(cur)[0]["n"]
    cur.execute("SELECT COUNT(*) as n FROM prix_history")
    nb_p = fetchall(cur)[0]["n"]
    cur.execute("""
        SELECT marque, COUNT(*) as nb, AVG(prix) as prix_moy, MIN(prix) as prix_min, MAX(prix) as prix_max
        FROM prix_history GROUP BY marque ORDER BY nb DESC
    """)
    niches = fetchall(cur)
    conn.close()
    return {"annonces": nb_a, "prix_history": nb_p, "niches": niches}
