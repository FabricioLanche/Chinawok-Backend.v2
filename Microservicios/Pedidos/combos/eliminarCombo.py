import json
import boto3
import os
from boto3.dynamodb.conditions import Attr
from utils.cors_utils import get_cors_headers

# Clientes DynamoDB
dynamodb = boto3.resource('dynamodb')

table_combos = dynamodb.Table(os.environ.get('TABLE_COMBOS', 'ChinaWok-Combos'))
table_ofertas = dynamodb.Table(os.environ.get('TABLE_OFERTAS', 'ChinaWok-Ofertas'))


def eliminar_ofertas_relacionadas(local_id, combo_id):
    """Elimina todas las ofertas que referencian el combo eliminado"""
    try:
        # Scan para encontrar ofertas del combo
        response = table_ofertas.scan(
            FilterExpression=Attr('local_id').eq(local_id) & Attr('combo_id').eq(combo_id)
        )
        
        ofertas_eliminadas = []
        for oferta in response.get('Items', []):
            # Eliminar la oferta
            table_ofertas.delete_item(
                Key={
                    'local_id': oferta['local_id'],
                    'oferta_id': oferta['oferta_id']
                }
            )
            ofertas_eliminadas.append(oferta['oferta_id'])
        
        return ofertas_eliminadas
    
    except Exception as e:
        print(f"Error eliminando ofertas relacionadas: {str(e)}")
        return []


def handler(event, context):
    """
    Lambda handler para eliminar un combo y todas sus referencias
    Elimina automáticamente:
    - El combo
    - Ofertas que lo referencian
    """
    try:
        # Obtener parámetros GET / DELETE
        params = event.get('queryStringParameters') or {}
        path_params = event.get('pathParameters') or {}
        
        # Obtener del body si viene por POST/DELETE
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

        combo_id = (
            params.get('combo_id')
            or path_params.get('combo_id')
            or body.get('combo_id')
        )
        
        if not local_id or not combo_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'Se requieren local_id y combo_id'
                })
            }
        
        # Verificar existencia
        response = table_combos.get_item(
            Key={
                'local_id': local_id,
                'combo_id': combo_id
            }
        )
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'Combo no encontrado'
                })
            }
        
        combo = response['Item']
        
        # 1. Eliminar ofertas relacionadas
        ofertas_eliminadas = eliminar_ofertas_relacionadas(local_id, combo_id)
        
        # 2. Eliminar el combo
        table_combos.delete_item(
            Key={
                'local_id': local_id,
                'combo_id': combo_id
            }
        )
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'message': 'Combo y referencias eliminadas exitosamente',
                'data': {
                    'combo': {
                        'local_id': local_id,
                        'combo_id': combo_id
                    },
                    'referencias_eliminadas': {
                        'ofertas': len(ofertas_eliminadas),
                        'ofertas_ids': ofertas_eliminadas
                    }
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