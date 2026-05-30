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
CONTAINER_NAME = "productos"

def get_container():
    client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    db = client.get_database_client(DATABASE_NAME)
    return db.get_container_client(CONTAINER_NAME)

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Products function triggered.")
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
            product_id = req.params.get("id")
            if product_id:
                item = container.read_item(item=product_id, partition_key=product_id)
                return func.HttpResponse(json.dumps(item), headers=headers)
            else:
                items = list(container.read_all_items())
                return func.HttpResponse(json.dumps(items), headers=headers)

        elif req.method == "POST":
            body = req.get_json()
            product = {
                "id": str(uuid.uuid4()),
                "nombre": body.get("nombre", ""),
                "categoria": body.get("categoria", ""),
                "precio_referencia": body.get("precio_referencia", 0),
                "tienda": body.get("tienda", ""),
                "url": body.get("url", ""),
                "creado_en": datetime.utcnow().isoformat()
            }
            container.create_item(product)
            return func.HttpResponse(json.dumps(product), status_code=201, headers=headers)

        elif req.method == "DELETE":
            product_id = req.params.get("id")
            if not product_id:
                return func.HttpResponse(json.dumps({"error": "id requerido"}), status_code=400, headers=headers)
            container.delete_item(item=product_id, partition_key=product_id)
            return func.HttpResponse(json.dumps({"mensaje": "Producto eliminado"}), headers=headers)

        else:
            return func.HttpResponse(json.dumps({"error": "Método no permitido"}), status_code=405, headers=headers)

    except exceptions.CosmosResourceNotFoundError:
        return func.HttpResponse(json.dumps({"error": "Producto no encontrado"}), status_code=404, headers=headers)
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, headers=headers)
