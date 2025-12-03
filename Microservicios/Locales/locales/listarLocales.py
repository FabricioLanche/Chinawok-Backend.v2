import os, json, boto3
from utils.cors_utils import get_cors_headers  # <-- importar CORS

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
        # Realizamos un scan de los locales (página completa)
        resp = table.scan()
        items = resp.get("Items", [])
        return _resp(200, items, headers)
    except Exception as e:
        return _resp(500, {"message": "Error al listar los locales", "error": str(e)}, headers)

def _resp(status, body, headers):
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body, ensure_ascii=False)
    }
