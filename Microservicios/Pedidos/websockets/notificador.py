import json
import boto3
import os
from datetime import datetime

# Clientes AWS
dynamodb = boto3.resource('dynamodb')
apigateway = boto3.client('apigatewaymanagementapi')

# Tablas
conexiones_table = dynamodb.Table(os.environ.get('TABLE_CONEXIONES', 'ChinaWok-WebSocket-Conexiones'))

def enviar_notificacion_pedido(pedido_id, usuario_correo, tipo_evento, datos):
    """
    Envía notificación WebSocket a un usuario específico sobre un pedido
    
    Args:
        pedido_id: ID del pedido
        usuario_correo: Email del usuario
        tipo_evento: Tipo de evento (ej: 'ESTADO_CAMBIADO', 'PEDIDO_LISTO')
        datos: Diccionario con datos del evento
    
    Returns:
        bool: True si se envió exitosamente, False si no
    """
    try:
        # Buscar conexión activa del usuario para este pedido
        response = conexiones_table.get_item(
            Key={
                'usuario_correo': usuario_correo,
                'pedido_id': pedido_id
            }
        )
        
        if 'Item' not in response:
            print(f'⚠️  Usuario {usuario_correo} no está conectado al pedido {pedido_id}')
            return False
        
        connection_id = response['Item']['connection_id']
        
        # Obtener WebSocket API endpoint desde variable de entorno
        websocket_url = os.environ.get('WEBSOCKET_API_ENDPOINT')
        if not websocket_url:
            print('❌ WEBSOCKET_API_ENDPOINT no configurado')
            return False
        
        # Configurar cliente de API Gateway Management con el endpoint correcto
        apigateway_client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=websocket_url
        )
        
        # Preparar mensaje
        mensaje = {
            'tipo': tipo_evento,
            'pedido_id': pedido_id,
            'timestamp': datetime.now().isoformat(),
            'datos': datos
        }
        
        # Enviar mensaje
        apigateway_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(mensaje).encode('utf-8')
        )
        
        print(f'✅ Notificación enviada a {usuario_correo}:')
        print(f'   - Tipo: {tipo_evento}')
        print(f'   - Connection ID: {connection_id}')
        
        return True
        
    except apigateway_client.exceptions.GoneException:
        # Conexión cerrada, eliminar de la tabla
        print(f'⚠️  Conexión cerrada, eliminando registro')
        try:
            conexiones_table.delete_item(
                Key={
                    'usuario_correo': usuario_correo,
                    'pedido_id': pedido_id
                }
            )
        except:
            pass
        return False
        
    except Exception as e:
        print(f'❌ Error al enviar notificación WebSocket: {str(e)}')
        return False
