import os, json, boto3, logging
from utils.cors_utils import get_cors_headers  # <-- importar CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('TABLE_LOCALES', 'ChinaWok-Locales'))

def lambda_handler(event, context):
    headers = get_cors_headers()  # <-- CORS headers

    # Manejar preflight request
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"message": "CORS preflight successful"})
        }

    try:
        local_id = event.get('pathParameters', {}).get('local_id')
        
        if not local_id:
            return _resp(400, {"message": "Falta el parámetro 'local_id' en el path"}, headers)
        
        logger.info(f"Buscando local con local_id: {local_id}")
        logger.info(f"Tabla: {table.table_name}")
        logger.info(f"Key schema: {table.key_schema}")
        
        resp = table.get_item(Key={"local_id": local_id})
        item = resp.get("Item")
        
        if not item:
            return _resp(404, {"message": "Local no encontrado"}, headers)
        
        return _resp(200, item, headers)
        
    except Exception as e:
        logger.exception(f"Error al obtener local: {str(e)}")
        return _resp(500, {"message": "Error al obtener el local", "error": str(e)}, headers)

def _resp(status, body, headers):
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body, ensure_ascii=False)
    }
