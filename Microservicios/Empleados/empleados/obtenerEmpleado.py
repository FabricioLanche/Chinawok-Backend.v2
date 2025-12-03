import boto3
import json
import os
from decimal import Decimal
from utils.cors_utils import get_cors_headers   # 👉 Igual que en login

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_EMPLEADOS'])


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def lambda_handler(event, context):
    try:
        # Validación de pathParameters
        if 'pathParameters' not in event or event['pathParameters'] is None:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),   # 👉 CORS agregado
                'body': json.dumps({'error': 'Parámetros de ruta faltantes'})
            }

        local_id = event['pathParameters'].get('local_id')
        dni = event['pathParameters'].get('dni')

        if not local_id or not dni:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),   # 👉 CORS agregado
                'body': json.dumps({'error': 'local_id y dni son requeridos'})
            }

        response = table.get_item(Key={'local_id': local_id, 'dni': dni})

        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),   # 👉 CORS agregado
                'body': json.dumps({'error': 'Empleado no encontrado'})
            }

        return {
            'statusCode': 200,
            'headers': get_cors_headers(),       # 👉 CORS agregado
            'body': json.dumps(response['Item'], cls=DecimalEncoder)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),       # 👉 CORS agregado
            'body': json.dumps({'error': f'Error interno: {str(e)}'})
        }
