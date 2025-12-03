import json
import boto3
import os
from utils.cors_utils import get_cors_headers

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_OFERTAS', 'ChinaWok-Ofertas')
table = dynamodb.Table(table_name)


def handler(event, context):
    """
    Lambda handler para eliminar una oferta de DynamoDB
    """
    try:
        # Obtener parámetros
        params = event.get('queryStringParameters') or {}
        path_params = event.get('pathParameters') or {}
        
        # Intentar obtener de body si no está en params
        body = {}
        if event.get('body'):
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        
        local_id = (
            params.get('local_id')
            or path_params.get('local_id')
            or body.get('local_id')
        )

        oferta_id = (
            params.get('oferta_id')
            or path_params.get('oferta_id')
            or body.get('oferta_id')
        )
        
        if not local_id or not oferta_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'Se requieren local_id y oferta_id'
                })
            }
        
        # Verificar que la oferta existe antes de eliminar
        response = table.get_item(
            Key={
                'local_id': local_id,
                'oferta_id': oferta_id
            }
        )
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'Oferta no encontrada'
                })
            }
        
        # Eliminar la oferta
        table.delete_item(
            Key={
                'local_id': local_id,
                'oferta_id': oferta_id
            }
        )
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'message': 'Oferta eliminada exitosamente',
                'data': {
                    'local_id': local_id,
                    'oferta_id': oferta_id
                }
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
