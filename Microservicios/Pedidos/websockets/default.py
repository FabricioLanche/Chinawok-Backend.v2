import json

def handler(event, context):
    """
    Handler por defecto para mensajes WebSocket no manejados
    """
    print(f'📡 WebSocket Default Event: {json.dumps(event)}')
    
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Mensaje recibido'})
    }