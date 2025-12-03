import json
import boto3
import os
from boto3.dynamodb.conditions import Key, Attr
from utils.cors_utils import get_cors_headers  # <-- importar CORS

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_PRODUCTOS', 'ChinaWok-Productos')
table = dynamodb.Table(table_name)

def handler(event, context):
    headers = get_cors_headers()  # <-- CORS headers

    # Manejo de preflight OPTIONS
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"message": "CORS preflight successful"})
        }

    try:
        # Obtener parámetros de query
        params = event.get('queryStringParameters') or {}
        
        local_id = params.get('local_id')
        categoria = params.get('categoria')
        
        if not local_id or not categoria:
            return _resp(400, {'error': 'Parámetros requeridos: local_id y categoria'}, headers)
        
        # Escanear la tabla con un filtro por local_id y categoria
        response = table.scan(
            FilterExpression=Attr('local_id').eq(local_id) & Attr('categoria').eq(categoria)
        )
        
        if not response.get('Items'):
            return _resp(404, {'error': 'No se encontraron productos para la categoría especificada'}, headers)
            
        return _resp(200, {'data': response['Items'], 'count': len(response['Items'])}, headers)
            
    except Exception as e:
        return _resp(500, {'error': 'Error interno del servidor', 'message': str(e)}, headers)

def _resp(status, body, headers):
    return {
        'statusCode': status,
        'headers': headers,
        'body': json.dumps(body, default=str, ensure_ascii=False)
    }
