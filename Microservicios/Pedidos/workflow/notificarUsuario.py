import json
import boto3
import os
from websockets.notificador import enviar_notificacion_pedido

# Este lambda se encarga de notificar al usuario que su pedido ha llegado
# y guarda el taskToken para que pueda ser usado cuando el usuario confirme
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

def lambda_handler(event, context):
    """Lambda para notificar al usuario sobre la entrega y esperar confirmación"""
    print(f'Notificando usuario sobre entrega: {json.dumps(event)}')
    
    pedido_id = event.get('pedido_id')
    usuario_correo = event.get('usuario_correo')
    task_token = event.get('taskToken')
    
    if not pedido_id or not usuario_correo or not task_token:
        raise ValueError('Faltan parámetros requeridos')
    
    try:
        # Guardar el taskToken en DynamoDB para recuperarlo cuando el usuario confirme
        table = dynamodb.Table(os.environ['TABLE_PEDIDOS'])
        
        print(f'🔍 Intentando actualizar pedido en DynamoDB:')
        print(f'   - Table: {os.environ["TABLE_PEDIDOS"]}')
        print(f'   - local_id: {event.get("local_id")}')
        print(f'   - pedido_id: {pedido_id}')
        
        update_response = table.update_item(
            Key={
                'local_id': event.get('local_id'),
                'pedido_id': pedido_id
            },
            UpdateExpression='SET task_token = :token, esperando_confirmacion = :true',
            ExpressionAttributeValues={
                ':token': task_token,
                ':true': True
            },
            ReturnValues='ALL_NEW'
        )
        
        print(f'✅ DynamoDB Update exitoso!')
        print(f'📊 Atributos actualizados: {list(update_response.get("Attributes", {}).keys())}')
        
        # Verificar que los campos se guardaron
        if 'task_token' in update_response.get('Attributes', {}):
            print(f'✅ task_token CONFIRMADO en DynamoDB')
        else:
            print(f'⚠️ WARNING: task_token NO aparece en Attributes')
        
        # Enviar notificación WebSocket al usuario
        notificacion_enviada = enviar_notificacion_pedido(
            pedido_id=pedido_id,
            usuario_correo=usuario_correo,
            tipo_evento='PEDIDO_ENTREGADO',
            datos={
                'estado': 'entregado',
                'mensaje': '¡Tu pedido ha llegado a su destino!',
                'accion_requerida': 'CONFIRMAR_RECEPCION',
                'texto_boton': 'Confirmar Recepción',
                'repartidor_dni': event.get('repartidor_dni')
            }
        )
        
        if notificacion_enviada:
            print(f'✅ Notificación WebSocket enviada a {usuario_correo}')
        else:
            print(f'⚠️  Usuario no conectado por WebSocket, notificación no enviada')
        
        print(f'🔑 TaskToken guardado: {task_token[:20]}...')
        
        return {
            'statusCode': 200,
            'message': 'Notificación enviada, esperando confirmación del usuario',
            'pedido_id': pedido_id
        }
        
    except Exception as e:
        print(f'Error al notificar usuario: {str(e)}')
        raise
