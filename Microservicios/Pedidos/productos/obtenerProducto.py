import json
import boto3
import os
from boto3.dynamodb.conditions import Key
from utils.cors_utils import get_cors_headers  # <-- agregado

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_PRODUCTOS', 'ChinaWok-Productos')
table = dynamodb.Table(table_name)

def handler(event, context):
    """
    Lambda handler para leer productos de DynamoDB
    Soporta:
    - GET por local_id y nombre (específico)
    - GET por local_id (todos los productos de un local)
    """
    cors_headers = get_cors_headers()  # <-- agregado

    try:
        # Obtener parámetros de query o path
        params = event.get('queryStringParameters') or {}
        path_params = event.get('pathParameters') or {}
        
        local_id = params.get('local_id') or path_params.get('local_id')
        nombre = params.get('nombre') or path_params.get('nombre')
        
        if not local_id:
            return {
                'statusCode': 400,
                'headers': cors_headers,  # <-- reemplazado
                'body': json.dumps({'error': 'Parámetro requerido: local_id'})
            }
        
        # Si se proporciona nombre, obtener un producto específico
        if nombre:
            response = table.get_item(Key={'local_id': local_id, 'nombre': nombre})
            
            if 'Item' not in response:
                return {
                    'statusCode': 404,
                    'headers': cors_headers,  # <-- reemplazado
                    'body': json.dumps({'error': 'Producto no encontrado'})
                }
            
            return {
                'statusCode': 200,
                'headers': cors_headers,  # <-- reemplazado
                'body': json.dumps({'data': response['Item']}, default=str)
            }
        
        # Si solo se proporciona local_id, obtener todos los productos del local
        else:
            response = table.query(KeyConditionExpression=Key('local_id').eq(local_id))
            
            return {
                'statusCode': 200,
                'headers': cors_headers,  # <-- reemplazado
                'body': json.dumps({'data': response['Items'], 'count': len(response['Items'])}, default=str)
            }
            
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': cors_headers,  # <-- reemplazado
            'body': json.dumps({'error': 'Error interno del servidor', 'message': str(e)})
        }
