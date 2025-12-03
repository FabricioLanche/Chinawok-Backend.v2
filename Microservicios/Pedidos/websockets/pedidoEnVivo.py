import json
import boto3
import os
from datetime import datetime
from utils.cors_utils import get_cors_headers

dynamodb = boto3.resource('dynamodb')
conexiones_table = dynamodb.Table(os.environ.get('TABLE_CONEXIONES', 'ChinaWok-WebSocket-Conexiones'))

def handler(event, context):
    """
    Handler para conexión inicial de WebSocket
    Registra la conexión en DynamoDB
    """
    print(f'📡 WebSocket Connect Event: {json.dumps(event)}')
    
    connection_id = event['requestContext']['connectionId']
    
    # Obtener parámetros de query string
    query_params = event.get('queryStringParameters') or {}
    usuario_correo = query_params.get('usuario_correo')
    pedido_id = query_params.get('pedido_id')
    
    if not usuario_correo or not pedido_id:
        print('❌ Faltan parámetros: usuario_correo y pedido_id son requeridos')
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'usuario_correo y pedido_id son requeridos'})
        }
    
    try:
        # Guardar conexión en DynamoDB
        ttl = int(datetime.now().timestamp()) + 86400  # 24 horas
        
        conexiones_table.put_item(
            Item={
                'usuario_correo': usuario_correo,
                'pedido_id': pedido_id,
                'connection_id': connection_id,
                'connected_at': datetime.now().isoformat(),
                'ttl': ttl
            }
        )
        
        print(f'✅ Conexión registrada:')
        print(f'   - Usuario: {usuario_correo}')
        print(f'   - Pedido: {pedido_id}')
        print(f'   - Connection ID: {connection_id}')
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Conectado al tracking en vivo',
                'pedido_id': pedido_id
            })
        }
        
    except Exception as e:
        print(f'❌ Error al registrar conexión: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }