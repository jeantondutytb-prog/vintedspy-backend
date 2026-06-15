"""
VintedSpy — Scheduler toutes catégories
Scrape Vinted par catégorie (newest_first) sans filtre de marque.
"""
import asyncio, httpx, json, logging, os
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

log_path = Path("/tmp/vintedspy.log") if not (Path.home() / "Downloads").exists() else Path.home() / "Downloads" / "vintedspy.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(log_path)]
)
log = logging.getLogger("scheduler")

BASE = "https://www.vinted.fr"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
INTERVAL = int(os.getenv("SCAN_INTERVAL", "300"))

# Catégories Vinted FR — ID : nom
# On scrape les plus volumineuses pour couvrir tout Vinted
CATEGORIES = [
    {"id": 1904, "nom": "Vêtements femme"},
    {"id": 4,    "nom": "Hauts femme"},
    {"id": 1,    "nom": "Robes"},
    {"id": 3,    "nom": "Pantalons femme"},
    {"id": 2,    "nom": "Jupes"},
    {"id": 6,    "nom": "Manteaux femme"},
    {"id": 5,    "nom": "Vestes femme"},
    {"id": 1232, "nom": "Chaussures femme"},
    {"id": 1231, "nom": "Sacs"},
    {"id": 1236, "nom": "Accessoires femme"},
    {"id": 1229, "nom": "Vêtements homme"},
    {"id": 586,  "nom": "T-shirts homme"},
    {"id": 614,  "nom": "Chemises homme"},
    {"id": 613,  "nom": "Pulls homme"},
    {"id": 616,  "nom": "Jeans homme"},
    {"id": 619,  "nom": "Pantalons homme"},
    {"id": 1223, "nom": "Manteaux homme"},
    {"id": 1230, "nom": "Chaussures homme"},
    {"id": 2050, "nom": "Vêtements enfant"},
    {"id": 1696, "nom": "Électronique"},
    {"id": 2994, "nom": "Téléphones"},
    {"id": 3035, "nom": "Montres connectées"},
    {"id": 3060, "nom": "Appareils photo"},
    {"id": 2940, "nom": "Jeux vidéo"},
    {"id": 1476, "nom": "Sport"},
    {"id": 1480, "nom": "Maison"},
    {"id": 2,    "nom": "Bijoux"},
]

async def scraper_categorie(session, categorie, cookies_str, per_page=20):
    try:
        params = {
            "catalog_ids[]": categorie["id"],
            "order": "newest_first",
            "per_page": per_page,
            "page": 1,
        }
        r = await session.get(
            BASE + "/api/v2/catalog/items",
            params=params,
            headers={
                "User-Agent": UA,
                "Accept": "application/json",
                "Cookie": cookies_str,
                "Referer": BASE,
                "Accept-Language": "fr-FR,fr;q=0.9",
            },
            timeout=15,
        )
        if r.status_code != 200:
            log.warning(f"  {categorie['nom']}: HTTP {r.status_code}")
            return []
        items = r.json().get("items", [])
        annonces = []
        for item in items:
            try:
                prix_obj = item.get("price", {})
                prix = float(prix_obj.get("amount", prix_obj)) if isinstance(prix_obj, dict) else float(prix_obj)
                if prix <= 0:
                    continue
                annonces.append({
                    "id": int(item["id"]),
                    "titre": item.get("title", ""),
                    "marque": item.get("brand_title", "") or "Sans marque",
                    "taille": item.get("size_title", ""),
                    "prix": prix,
                    "nb_favoris": int(item.get("favourite_count", 0)),
                    "url": BASE + item.get("path", ""),
                    "photo": (item.get("photo") or {}).get("url", ""),
                    "vendeur": (item.get("user") or {}).get("login", ""),
                    "categorie": categorie["nom"],
                })
            except:
                pass
        return annonces
    except Exception as e:
        log.error(f"Erreur {categorie['nom']}: {e}")
        return []

async def get_cookies():
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as s:
        await s.get(BASE, headers={"User-Agent": UA, "Accept-Language": "fr-FR"})
        await asyncio.sleep(2)
        return "; ".join(f"{k}={v}" for k, v in dict(s.cookies).items()), s.cookies

async def run_scan():
    from database import init_db, sauvegarder_annonces, stats_db
    log.info(f"=== Scan {len(CATEGORIES)} catégories ===")

    try:
        cookies_str, jar = await get_cookies()
    except Exception as e:
        log.error(f"Cookies: {e}")
        return

    async with httpx.AsyncClient(follow_redirects=True, timeout=20, cookies=jar) as s:
        toutes = []
        for cat in CATEGORIES:
            annonces = await scraper_categorie(s, cat, cookies_str)
            log.info(f"  {cat['nom']}: {len(annonces)} annonces")
            toutes.extend(annonces)
            await asyncio.sleep(2)  # respecter le rate limit

    nouvelles = sauvegarder_annonces(toutes)
    stats = stats_db()
    log.info(f"Scan terminé — {nouvelles} nouvelles | DB: {stats['annonces']} annonces total")

async def main():
    from database import init_db
    init_db()
    log.info(f"Scheduler démarré — {len(CATEGORIES)} catégories — toutes les {INTERVAL//60} min")

    scan_count = 0
    while True:
        scan_count += 1
        log.info(f"--- Scan #{scan_count} ---")
        try:
            await run_scan()
        except Exception as e:
            log.error(f"Erreur scan #{scan_count}: {e}")
        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Scheduler arrêté.")
