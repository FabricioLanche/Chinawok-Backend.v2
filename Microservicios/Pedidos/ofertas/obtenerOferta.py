import json
import boto3
import os
from boto3.dynamodb.conditions import Key
from utils.cors_utils import get_cors_headers

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_OFERTAS', 'ChinaWok-Ofertas')
table = dynamodb.Table(table_name)


def handler(event, context):
    """
    Lambda handler para leer ofertas de DynamoDB
    Soporta:
    - GET por local_id y oferta_id (específico)
    - GET por local_id (todas las ofertas de un local)
    """
    try:
        # Obtener parámetros de query o path
        params = event.get('queryStringParameters') or {}
        path_params = event.get('pathParameters') or {}
        
        local_id = params.get('local_id') or path_params.get('local_id')
        oferta_id = params.get('oferta_id') or path_params.get('oferta_id')
        
        if not local_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'Parámetro requerido: local_id'
                })
            }
        
        # Si se proporciona oferta_id, obtener una oferta específica
        if oferta_id:
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
            
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'data': response['Item']
                }, default=str)
            }
        
        # Si solo se proporciona local_id, obtener todas las ofertas del local
        else:
            response = table.query(
                KeyConditionExpression=Key('local_id').eq(local_id)
            )
            
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'data': response['Items'],
                    'count': len(response['Items'])
                }, default=str)
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
