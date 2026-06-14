import asyncio, httpx, json

BASE = "https://www.vinted.fr"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"

async def main():
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as s:
        await s.get(BASE, headers={"User-Agent": UA, "Accept-Language": "fr-FR"})
        await asyncio.sleep(2)
        cookies_str = "; ".join(f"{k}={v}" for k, v in dict(s.cookies).items())
        r = await s.get(BASE + "/api/v2/catalog/items",
            params={"search_text": "levi 501", "order": "newest_first", "per_page": 20, "page": 1},
            headers={"User-Agent": UA, "Accept": "application/json", "Cookie": cookies_str, "Referer": BASE})
        
        items = r.json().get("items", [])
        print(f"\n{'='*55}")
        print(f"{len(items)} annonces Levi's 501 trouvées sur Vinted")
        print(f"{'='*55}")
        
        annonces = []
        for item in items:
            prix = float(item.get("price", {}).get("amount", 0))
            annonce = {
                "id": item["id"],
                "titre": item.get("title", ""),
                "marque": item.get("brand_title", ""),
                "taille": item.get("size_title", ""),
                "prix": prix,
                "nb_favoris": int(item.get("favourite_count", 0)),
                "url": BASE + item.get("path", ""),
                "photo": item.get("photo", {}).get("url", ""),
                "vendeur": item.get("user", {}).get("login", ""),
            }
            annonces.append(annonce)
            print(f"  {annonce['titre'][:50]}")
            print(f"  Prix: {annonce['prix']}€ | Taille: {annonce['taille']} | Favs: {annonce['nb_favoris']}")
            print(f"  {annonce['url']}")
            print()
        
        with open("annonces.json", "w") as f:
            json.dump(annonces, f, ensure_ascii=False, indent=2)
        print(f"Sauvegardé dans annonces.json")

asyncio.run(main())
