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
CONTAINER_NAME = "tiendas"

def get_container():
    client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    db = client.get_database_client(DATABASE_NAME)
    return db.get_container_client(CONTAINER_NAME)

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Stores function triggered.")
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json"
    }

    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=200, headers=headers)

    try:
        container = get_container()

        if req.method == "GET":
            store_id = req.params.get("id")
            if store_id:
                item = container.read_item(item=store_id, partition_key=store_id)
                return func.HttpResponse(json.dumps(item), headers=headers)
            else:
                items = list(container.read_all_items())
                return func.HttpResponse(json.dumps(items), headers=headers)

        elif req.method == "POST":
            body = req.get_json()
            store = {
                "id": str(uuid.uuid4()),
                "nombre": body.get("nombre", ""),
                "url_base": body.get("url_base", ""),
                "activa": body.get("activa", True),
                "creado_en": datetime.utcnow().isoformat()
            }
            container.create_item(store)
            return func.HttpResponse(json.dumps(store), status_code=201, headers=headers)

        elif req.method == "DELETE":
            store_id = req.params.get("id")
            if not store_id:
                return func.HttpResponse(json.dumps({"error": "id requerido"}), status_code=400, headers=headers)
            container.delete_item(item=store_id, partition_key=store_id)
            return func.HttpResponse(json.dumps({"mensaje": "Tienda eliminada"}), headers=headers)

        else:
            return func.HttpResponse(json.dumps({"error": "Método no permitido"}), status_code=405, headers=headers)

    except exceptions.CosmosResourceNotFoundError:
        return func.HttpResponse(json.dumps({"error": "Tienda no encontrada"}), status_code=404, headers=headers)
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, headers=headers)
