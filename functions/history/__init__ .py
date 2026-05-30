import logging
import json
import uuid
from datetime import datetime
import azure.functions as func
from azure.cosmos import CosmosClient, exceptions
import os

COSMOS_ENDPOINT = os.environ.get("COSMOS_ENDPOINT", "")
COSMOS_KEY = os.environ.get("COSMOS_KEY", "")
DATABASE_NAME = "PriceComparatorDB"
CONTAINER_NAME = "precios"

def get_container():
    client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    db = client.get_database_client(DATABASE_NAME)
    return db.get_container_client(CONTAINER_NAME)

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("History function triggered.")
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json"
    }

    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=200, headers=headers)

    try:
        container = get_container()
        product_id = req.params.get("producto_id")
        store_id = req.params.get("tienda_id")

        if product_id and store_id:
            # History for a specific product in a specific store
            query = f"""
                SELECT * FROM c
                WHERE c.producto_id = '{product_id}'
                AND c.tienda_id = '{store_id}'
                ORDER BY c.fecha DESC
                OFFSET 0 LIMIT 90
            """
        elif product_id:
            # History for a product across all stores (for comparison)
            query = f"""
                SELECT * FROM c
                WHERE c.producto_id = '{product_id}'
                ORDER BY c.fecha DESC
                OFFSET 0 LIMIT 200
            """
        else:
            return func.HttpResponse(
                json.dumps({"error": "producto_id es requerido"}),
                status_code=400, headers=headers
            )

        items = list(container.query_items(query=query, enable_cross_partition_query=True))

        # Group by store for the comparison view
        by_store = {}
        for item in items:
            tid = item.get("tienda_id", "unknown")
            if tid not in by_store:
                by_store[tid] = {
                    "tienda_id": tid,
                    "tienda_nombre": item.get("tienda_nombre", tid),
                    "precios": []
                }
            by_store[tid]["precios"].append({
                "precio": item.get("precio", 0),
                "disponible": item.get("disponible", True),
                "fecha": item.get("fecha", ""),
                "url": item.get("url", "")
            })

        result = {
            "producto_id": product_id,
            "tiendas": list(by_store.values())
        }
        return func.HttpResponse(json.dumps(result), headers=headers)

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, headers=headers)
