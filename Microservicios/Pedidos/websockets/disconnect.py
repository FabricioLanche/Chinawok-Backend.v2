import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
conexiones_table = dynamodb.Table(os.environ.get('TABLE_CONEXIONES', 'ChinaWok-WebSocket-Conexiones'))

def handler(event, context):
    """
    Handler para desconexión de WebSocket
    Elimina la conexión de DynamoDB
    """
    print(f'📡 WebSocket Disconnect Event: {json.dumps(event)}')
    
    connection_id = event['requestContext']['connectionId']
    
    try:
        # Buscar y eliminar todas las conexiones con este connection_id
        response = conexiones_table.scan(
            FilterExpression='connection_id = :cid',
            ExpressionAttributeValues={':cid': connection_id}
        )
        
        for item in response.get('Items', []):
            conexiones_table.delete_item(
                Key={
                    'usuario_correo': item['usuario_correo'],
                    'pedido_id': item['pedido_id']
                }
            )
            print(f'✅ Conexión eliminada: {item["usuario_correo"]} - {item["pedido_id"]}')
        
        return {'statusCode': 200}
        
    except Exception as e:
        print(f'❌ Error al eliminar conexión: {str(e)}')
        return {'statusCode': 500}