import logging
import json
import uuid
from datetime import datetime
import azure.functions as func
from azure.cosmos import CosmosClient
import os
import requests
from bs4 import BeautifulSoup
import re
import time

COSMOS_ENDPOINT = os.environ.get("COSMOS_ENDPOINT", "")
COSMOS_KEY = os.environ.get("COSMOS_KEY", "")
DATABASE_NAME = "PriceComparatorDB"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def get_container(name: str):
    client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    db = client.get_database_client(DATABASE_NAME)
    return db.get_container_client(name)


def clean_price(raw: str) -> float:
    """Remove currency symbols and separators, return float."""
    if not raw:
        return 0.0
    cleaned = re.sub(r"[^\d,.]", "", raw.strip())
    # Colombian format uses dots as thousands separator: 1.299.000
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


# ─── Scraper: Alkosto ────────────────────────────────────────────────────────

def scrape_alkosto(url: str) -> dict:
    """
    Scrapes a single Alkosto product page.
    Returns dict with keys: precio, disponible, nombre.
    """
    result = {"precio": 0.0, "disponible": False, "nombre": ""}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Price — Alkosto uses a span with itemprop="price" or class containing "price"
        price_tag = soup.find("span", {"itemprop": "price"})
        if not price_tag:
            price_tag = soup.find("p", class_=re.compile(r"price", re.I))
        if not price_tag:
            price_tag = soup.find("span", class_=re.compile(r"price", re.I))

        if price_tag:
            result["precio"] = clean_price(price_tag.get_text())

        # Availability
        avail = soup.find(attrs={"itemprop": "availability"})
        if avail:
            result["disponible"] = "InStock" in avail.get("content", "") or "instock" in avail.get("href", "").lower()
        else:
            add_btn = soup.find("button", string=re.compile(r"agregar|carrito|comprar", re.I))
            result["disponible"] = add_btn is not None

        # Name
        name_tag = soup.find("h1", {"itemprop": "name"}) or soup.find("h1")
        if name_tag:
            result["nombre"] = name_tag.get_text(strip=True)[:200]

    except Exception as e:
        logging.warning(f"Alkosto scrape failed for {url}: {e}")

    return result


# ─── Scraper: Falabella ──────────────────────────────────────────────────────

def scrape_falabella(url: str) -> dict:
    """
    Scrapes a single Falabella product page.
    Returns dict with keys: precio, disponible, nombre.
    """
    result = {"precio": 0.0, "disponible": False, "nombre": ""}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Falabella embeds JSON-LD with product data
        json_ld = soup.find("script", {"type": "application/ld+json"})
        if json_ld:
            data = json.loads(json_ld.string or "{}")
            offers = data.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0]
            price_str = str(offers.get("price", "0"))
            result["precio"] = clean_price(price_str)
            result["disponible"] = "InStock" in offers.get("availability", "")
            result["nombre"] = data.get("name", "")[:200]
        else:
            # Fallback: CSS selectors
            price_tag = soup.find("span", class_=re.compile(r"copy10|price", re.I))
            if price_tag:
                result["precio"] = clean_price(price_tag.get_text())
            name_tag = soup.find("h1")
            if name_tag:
                result["nombre"] = name_tag.get_text(strip=True)[:200]
            result["disponible"] = soup.find("button", string=re.compile(r"agregar|carrito", re.I)) is not None

    except Exception as e:
        logging.warning(f"Falabella scrape failed for {url}: {e}")

    return result


STORE_SCRAPERS = {
    "alkosto": scrape_alkosto,
    "falabella": scrape_falabella,
}


# ─── Main Timer Trigger ──────────────────────────────────────────────────────

def main(mytimer: func.TimerRequest) -> None:
    utc_now = datetime.utcnow()
    logging.info(f"Scraper Timer Trigger fired at {utc_now}")

    try:
        products_container = get_container("productos")
        stores_container = get_container("tiendas")
        prices_container = get_container("precios")

        products = list(products_container.read_all_items())
        stores = {s["id"]: s for s in stores_container.read_all_items()}

        scraped = 0
        errors = 0

        for product in products:
            url = product.get("url", "")
            store_id = product.get("tienda", "")
            store = stores.get(store_id, {})
            store_name = store.get("nombre", store_id).lower()

            # Pick the right scraper by store name keyword
            scraper_fn = None
            for key, fn in STORE_SCRAPERS.items():
                if key in store_name:
                    scraper_fn = fn
                    break

            if not scraper_fn or not url:
                logging.warning(f"No scraper or URL for product {product.get('id')}. Skipping.")
                continue

            time.sleep(1)  # Be polite between requests
            scraped_data = scraper_fn(url)

            if scraped_data["precio"] > 0:
                price_record = {
                    "id": str(uuid.uuid4()),
                    "producto_id": product["id"],
                    "producto_nombre": product.get("nombre", ""),
                    "tienda_id": store_id,
                    "tienda_nombre": store.get("nombre", store_id),
                    "precio": scraped_data["precio"],
                    "disponible": scraped_data["disponible"],
                    "url": url,
                    "fecha": utc_now.isoformat()
                }
                prices_container.create_item(price_record)
                scraped += 1
                logging.info(
                    f"✓ Saved price {scraped_data['precio']} for "
                    f"'{product.get('nombre')}' @ {store.get('nombre')}"
                )
            else:
                errors += 1
                logging.warning(f"✗ Could not extract price for '{product.get('nombre')}' @ {url}")

        logging.info(f"Scraper finished — {scraped} saved, {errors} failed.")

    except Exception as e:
        logging.error(f"Scraper fatal error: {e}")
        raise
