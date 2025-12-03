import json
import boto3
import os
from boto3.dynamodb.conditions import Key
from utils.cors_utils import get_cors_headers  # <-- agregado

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_PEDIDOS', 'ChinaWok-Pedidos')
table = dynamodb.Table(table_name)


def handler(event, context):
    """
    Lambda handler para leer pedidos de DynamoDB
    Soporta:
    - GET por local_id y pedido_id (específico)
    - GET por local_id (todos los pedidos de un local)
    """
    cors_headers = get_cors_headers()  # <-- agregado

    try:
        # Obtener parámetros de query o path
        params = event.get('queryStringParameters') or {}
        path_params = event.get('pathParameters') or {}

        local_id = params.get('local_id') or path_params.get('local_id')
        pedido_id = params.get('pedido_id') or path_params.get('pedido_id')

        if not local_id:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({
                    'error': 'Parámetro requerido: local_id'
                })
            }

        # Si se proporciona pedido_id, obtener un pedido específico
        if pedido_id:
            response = table.get_item(
                Key={
                    'local_id': local_id,
                    'pedido_id': pedido_id
                }
            )

            if 'Item' not in response:
                return {
                    'statusCode': 404,
                    'headers': cors_headers,
                    'body': json.dumps({
                        'error': 'Pedido no encontrado'
                    })
                }

            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({
                    'data': response['Item']
                }, default=str)
            }


        # Si solo se proporciona local_id, obtener todos los pedidos del local
        else:
            response = table.query(
                KeyConditionExpression=Key('local_id').eq(local_id)
            )
            
            # Ordenar pedidos por fecha_creacion (más recientes primero)
            pedidos = response['Items']
            pedidos_ordenados = sorted(
                pedidos,
                key=lambda x: x.get('fecha_creacion', ''),
                reverse=True  # Descendente: más recientes primero
            )

            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({
                    'data': pedidos_ordenados,
                    'count': len(pedidos_ordenados)
                }, default=str)
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({
                'error': 'Error interno del servidor',
                'message': str(e)
            })
        }
