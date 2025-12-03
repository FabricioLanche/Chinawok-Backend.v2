import json
import boto3
import os
from utils.dynamodb_helper import (
    obtener_pedido,
    marcar_empleado_libre,
    finalizar_pedido
)
from utils.cors_utils import get_cors_headers
from websockets.notificador import enviar_notificacion_pedido

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
stepfunctions = boto3.client('stepfunctions', region_name='us-east-1')

def lambda_handler(event, context):
    """Lambda para procesar la confirmación del usuario y liberar empleados con CORS"""
    body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event
    
    local_id = body.get('local_id')
    pedido_id = body.get('pedido_id')
    confirmado = body.get('confirmado', True)
    repartidor_dni = body.get('repartidor_dni')  # opcional
    
    if not local_id or not pedido_id:
        return {
            'statusCode': 400,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': 'Faltan parámetros requeridos'})
        }
    
    try:
        # Obtener el pedido
        pedido = obtener_pedido(local_id, pedido_id)
        if not pedido:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': 'Pedido no encontrado'})
            }
        
        historial = pedido.get('historial_estados', [])
        empleados_liberados = []

        # Liberar empleados activos del historial
        for estado in historial:
            if estado.get('activo') and estado.get('empleado'):
                empleado = estado['empleado']
                try:
                    marcar_empleado_libre(local_id, empleado['dni'])
                    empleados_liberados.append(empleado['dni'])
                except Exception as e:
                    print(f'Error liberando empleado {empleado["dni"]}: {str(e)}')

        # Liberar repartidor adicional si aplica
        if repartidor_dni and repartidor_dni not in empleados_liberados:
            try:
                marcar_empleado_libre(local_id, repartidor_dni)
            except Exception as e:
                print(f'Error liberando repartidor adicional {repartidor_dni}: {str(e)}')
        
        # Finalizar pedido y liberar empleados
        pedido_actualizado = finalizar_pedido(local_id, pedido_id)

        # Enviar éxito a Step Functions si había taskToken
        task_token = pedido.get('task_token')
        if task_token:
            stepfunctions.send_task_success(
                taskToken=task_token,
                output=json.dumps({'confirmado': confirmado})
            )
            table = dynamodb.Table(os.environ['TABLE_PEDIDOS'])
            table.update_item(
                Key={'local_id': local_id, 'pedido_id': pedido_id},
                UpdateExpression='REMOVE task_token, esperando_confirmacion'
            )

        # Enviar notificación WebSocket
        enviar_notificacion_pedido(
            pedido_id=pedido_id,
            usuario_correo=pedido.get('usuario_correo'),
            tipo_evento='PEDIDO_COMPLETADO',
            datos={
                'estado': 'recibido',
                'mensaje': '¡Gracias por confirmar! Disfruta tu pedido 🥡'
            }
        )

        # Response simple con CORS
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'message': 'Confirmación procesada exitosamente',
                'pedido_id': pedido_id
            })
        }
    
    except Exception as e:
        print(f'Error al procesar confirmación: {str(e)}')
        import traceback
        print(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': str(e)})
        }
