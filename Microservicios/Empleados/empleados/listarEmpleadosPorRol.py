import boto3
import json
import os
from boto3.dynamodb.conditions import Key
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
        # Validar pathParameters
        if 'pathParameters' not in event or event['pathParameters'] is None:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),  # 👉 CORS agregado
                'body': json.dumps({'error': 'Parámetros de ruta faltantes'})
            }

        local_id = event['pathParameters'].get('local_id')
        role = event['pathParameters'].get('role')

        if not local_id or not role:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),  # 👉 CORS agregado
                'body': json.dumps({'error': 'local_id y role son requeridos'})
            }

        response = table.query(
            KeyConditionExpression=Key('local_id').eq(local_id),
            FilterExpression='#r = :role',
            ExpressionAttributeNames={'#r': 'role'},
            ExpressionAttributeValues={':role': role}
        )

        return {
            'statusCode': 200,
            'headers': get_cors_headers(),  # 👉 CORS agregado
            'body': json.dumps(response.get('Items', []), cls=DecimalEncoder)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),  # 👉 CORS agregado
            'body': json.dumps({'error': str(e)})
        }
