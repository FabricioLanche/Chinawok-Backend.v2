import json
from utils.dynamodb_helper import (
    obtener_pedido,
    marcar_empleado_libre,
    finalizar_pedido
)
from utils.json_encoder import json_dumps

def lambda_handler(event, context):
    """Lambda para confirmar la entrega del pedido"""
    print(f'Iniciando proceso de confirmar: {json.dumps(event)}')
    
    # Manejar invocación desde API Gateway (HTTP) o Step Functions (directo)
    if 'body' in event:
        body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
    else:
        body = event
    
    local_id = body.get('local_id')
    pedido_id = body.get('pedido_id')
    repartidor_dni = body.get('repartidor_dni')
    
    if not local_id or not pedido_id:
        raise ValueError('Faltan parámetros requeridos: local_id o pedido_id')
    
    try:
        # Obtener información del pedido
        pedido = obtener_pedido(local_id, pedido_id)
        usuario_correo = pedido.get('usuario_correo')
        
        # Validar que el pedido esté en estado "enviando"
        if pedido.get('estado') != 'enviando':
            raise ValueError(f'El pedido debe estar en estado "enviando", actualmente está en "{pedido.get("estado")}"')
        
        # Buscar TODOS los empleados activos en el historial y liberarlos
        historial = pedido.get('historial_estados', [])
        empleados_liberados = []
        
        for estado in historial:
            if estado.get('activo') and estado.get('empleado'):
                empleado = estado['empleado']
                empleado_dni = empleado.get('dni')
                empleado_rol = empleado.get('rol', '').lower()
                
                try:
                    marcar_empleado_libre(local_id, empleado_dni)
                    empleados_liberados.append({
                        'dni': empleado_dni,
                        'rol': empleado_rol
                    })
                    print(f'Empleado {empleado_rol} {empleado_dni} liberado')
                except Exception as e:
                    print(f'Error liberando empleado {empleado_dni}: {str(e)}')
        
        # Si se proporcionó un repartidor_dni específico y no fue liberado arriba, liberarlo
        if repartidor_dni and not any(e['dni'] == repartidor_dni for e in empleados_liberados):
            try:
                marcar_empleado_libre(local_id, repartidor_dni)
                empleados_liberados.append({
                    'dni': repartidor_dni,
                    'rol': 'repartidor'
                })
                print(f'Repartidor adicional {repartidor_dni} liberado')
            except Exception as e:
                print(f'Error liberando repartidor adicional {repartidor_dni}: {str(e)}')
        
        if not empleados_liberados:
            print('Advertencia: No se encontraron empleados activos para liberar')
        else:
            print(f'Total empleados liberados: {len(empleados_liberados)}')
        
        # Finalizar pedido (actualizar estado a recibido y cerrar historial)
        pedido_actualizado = finalizar_pedido(local_id, pedido_id)

        print(f'Pedido confirmado y completado: {pedido_id}')
        
        result = {
            'message': 'Pedido completado exitosamente',
            'pedido_id': pedido_id,
            'local_id': local_id,
            'estado': 'recibido',
            'empleados_liberados': len(empleados_liberados),
            'historial_estados': pedido_actualizado.get('historial_estados', pedido.get('historial_estados', [])),
            'pedido_completo': pedido_actualizado
        }
        
        if 'body' in event:
            return {
                'statusCode': 200,
                'body': json_dumps(result),
                'headers': {'Content-Type': 'application/json'}
            }
        
        return result
        
    except Exception as e:
        print(f'Error en lambda confirmar: {str(e)}')
        import traceback
        print(f'Traceback: {traceback.format_exc()}')
        
        if 'body' in event:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)}),
                'headers': {'Content-Type': 'application/json'}
            }
        raise