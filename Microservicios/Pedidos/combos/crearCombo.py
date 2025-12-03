import json
import boto3
import os
import uuid
from decimal import Decimal
from utils.cors_utils import get_cors_headers   # <-- se agrega igual que en login

dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_COMBOS', 'ChinaWok-Combos')
table = dynamodb.Table(table_name)


def handler(event, context):
    """
    Lambda handler para crear un combo en DynamoDB
    """
    try:
        # Parsear body al mismo estilo que login
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", event)

        # Validación de campos requeridos
        campos_requeridos = ['local_id', 'nombre', 'productos_nombres']
        for campo in campos_requeridos:
            if campo not in body:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'error': f'Campo requerido faltante: {campo}'
                    })
                }

        # productos_nombres debe ser array no vacío
        if not isinstance(body.get('productos_nombres'), list) or len(body['productos_nombres']) == 0:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'productos_nombres debe ser un array con al menos un elemento'
                })
            }

        # Generar UUID
        body['combo_id'] = str(uuid.uuid4())

        # Guardar en DynamoDB
        table.put_item(Item=body)

        return {
            'statusCode': 201,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'message': 'Combo creado exitosamente',
                'data': body
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Error interno del servidor',
                'message': str(e)
            })
        }
