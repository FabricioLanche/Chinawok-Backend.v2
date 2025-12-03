import json
import boto3
import os
from utils.cors_utils import get_cors_headers  # <-- agregado

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_PEDIDOS', 'ChinaWok-Pedidos')
table = dynamodb.Table(table_name)

# Tabla de usuarios
usuarios_table_name = os.environ.get('TABLE_USUARIOS', 'ChinaWok-Usuarios')
usuarios_table = dynamodb.Table(usuarios_table_name)


def handler(event, context):
    """
    Lambda handler para eliminar un pedido de DynamoDB
    """
    cors_headers = get_cors_headers()  # <-- agregado

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

        pedido_id = (
            params.get('pedido_id')
            or path_params.get('pedido_id')
            or body.get('pedido_id')
        )

        if not local_id or not pedido_id:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({
                    'error': 'Se requieren local_id y pedido_id'
                })
            }

        # Verificar que el pedido existe antes de eliminar
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
        
        # Obtener datos del pedido antes de eliminar
        pedido = response['Item']
        usuario_correo = pedido.get('usuario_correo')

        # Eliminar el pedido
        table.delete_item(
            Key={
                'local_id': local_id,
                'pedido_id': pedido_id
            }
        )
        
        # Eliminar del historial del usuario
        if usuario_correo:
            try:
                # Obtener usuario actual
                user_response = usuarios_table.get_item(Key={'correo': usuario_correo})
                if 'Item' in user_response:
                    usuario = user_response['Item']
                    historial = usuario.get('historial_pedidos', [])
                    
                    # Remover pedido_id del historial
                    if pedido_id in historial:
                        historial.remove(pedido_id)
                        
                        # Actualizar usuario
                        usuarios_table.update_item(
                            Key={'correo': usuario_correo},
                            UpdateExpression='SET historial_pedidos = :historial',
                            ExpressionAttributeValues={':historial': historial}
                        )
            except Exception as e:
                # Log error pero no fallar la eliminación del pedido
                print(f"Warning: No se pudo actualizar historial de usuario: {str(e)}")

        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'message': 'Pedido eliminado exitosamente',
                'data': {
                    'local_id': local_id,
                    'pedido_id': pedido_id
                }
            })
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
