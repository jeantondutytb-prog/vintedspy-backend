"""
Trakr — Main
Lance le scraper, stocke en base, affiche les opportunités scorées.
"""
import asyncio, httpx, json, time
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

BASE = "https://www.vinted.fr"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"

NICHES = [
    "levi 501",
    "nike air force 1",
    "north face",
    "carhartt",
]

async def scraper_niche(session: httpx.AsyncClient, search: str, cookies_str: str) -> list[dict]:
    r = await session.get(
        BASE + "/api/v2/catalog/items",
        params={"search_text": search, "order": "newest_first", "per_page": 20, "page": 1},
        headers={"User-Agent": UA, "Accept": "application/json",
                 "Cookie": cookies_str, "Referer": BASE}
    )
    if r.status_code != 200:
        print(f"  Erreur {r.status_code} pour '{search}'")
        return []

    items = r.json().get("items", [])
    annonces = []
    for item in items:
        try:
            prix_obj = item.get("price", {})
            prix = float(prix_obj.get("amount", prix_obj)) if isinstance(prix_obj, dict) else float(prix_obj)
            annonces.append({
                "id": int(item["id"]),
                "titre": item.get("title", ""),
                "marque": item.get("brand_title", ""),
                "taille": item.get("size_title", ""),
                "prix": prix,
                "nb_favoris": int(item.get("favourite_count", 0)),
                "url": BASE + item.get("path", ""),
                "photo": (item.get("photo") or {}).get("url", ""),
                "vendeur": (item.get("user") or {}).get("login", ""),
            })
        except Exception as e:
            pass
    return annonces

async def scrape_tout() -> list[dict]:
    print("Connexion à Vinted...")
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as s:
        await s.get(BASE, headers={"User-Agent": UA, "Accept-Language": "fr-FR"})
        await asyncio.sleep(2)
        cookies_str = "; ".join(f"{k}={v}" for k, v in dict(s.cookies).items())
        print(f"Cookies OK : {len(dict(s.cookies))} cookies\n")

        toutes = []
        for niche in NICHES:
            print(f"Scraping '{niche}'...")
            annonces = await scraper_niche(s, niche, cookies_str)
            print(f"  {len(annonces)} annonces")
            toutes.extend(annonces)
            await asyncio.sleep(3)

        return toutes

def afficher_opportunites(opps: list[dict]):
    print(f"\n{'='*65}")
    print(f"TOP OPPORTUNITÉS — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*65}")

    if not opps:
        print("Pas encore assez de données pour calculer les médianes.")
        print("Lance le script encore 2-3 fois pour accumuler l'historique.")
        return

    for i, o in enumerate(opps[:10], 1):
        print(f"\n#{i} [{o['score']}/100] {o['titre'][:50]}")
        print(f"   Prix: {o['prix']}€  |  Médiane marché: {o['prix_median']}€  |  Écart: -{o['ecart_pct']}%")
        print(f"   Marge nette estimée: {o['marge_nette']}€  |  Favs: {o['nb_favoris']}")
        print(f"   {o['url']}")

async def main():
    # Import ici pour éviter les erreurs si le fichier n'est pas encore là
    try:
        from database import init_db, sauvegarder_annonces, get_opportunites, stats_db
    except ImportError:
        print("database.py introuvable — place-le dans le même dossier que main.py")
        return

    # Init DB
    init_db()

    # Scrape
    annonces = await scrape_tout()
    print(f"\nTotal: {len(annonces)} annonces récupérées")

    # Sauvegarde
    nouvelles = sauvegarder_annonces(annonces)
    print(f"{nouvelles} nouvelles annonces ajoutées en base")

    # Stats
    stats = stats_db()
    print(f"Base de données : {stats['annonces']} annonces | {stats['prix_history']} entrées historique")

    # Opportunités scorées
    opps = get_opportunites()
    afficher_opportunites(opps)

    # Sauvegarder aussi en JSON pour debug
    with open(Path.home() / "Downloads" / "opportunites.json", "w") as f:
        json.dump(opps, f, ensure_ascii=False, indent=2)
    print(f"\nSauvegardé dans ~/Downloads/opportunites.json")

if __name__ == "__main__":
    asyncio.run(main())
