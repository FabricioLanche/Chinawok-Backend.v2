import json
from utils.dynamodb_helper import (
    obtener_pedido,
    buscar_empleado_disponible,
    marcar_empleado_ocupado,
    marcar_empleado_libre,
    actualizar_estado_pedido_con_empleado
)
from utils.json_encoder import json_dumps
from websockets.notificador import enviar_notificacion_pedido

def lambda_handler(event, context):
    """Lambda para asignar repartidor y enviar el pedido"""
    print(f'Iniciando proceso de enviar: {json.dumps(event)}')
    
    # Manejar invocación desde API Gateway (HTTP) o Step Functions (directo)
    if 'body' in event:
        body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
    else:
        body = event
    
    local_id = body.get('local_id')
    pedido_id = body.get('pedido_id')
    despachador_dni = body.get('despachador_dni')
    
    if not local_id or not pedido_id:
        raise ValueError('Faltan parámetros requeridos: local_id o pedido_id')
    
    try:
        # Obtener información del pedido
        pedido = obtener_pedido(local_id, pedido_id)
        
        # Validar que el pedido esté en estado "empacando"
        if pedido.get('estado') != 'empacando':
            raise ValueError(f'El pedido debe estar en estado "empacando", actualmente está en "{pedido.get("estado")}"')
        
        # Buscar e intentar asignar repartidor disponible con fallback
        repartidor = None
        repartidores_disponibles = buscar_empleado_disponible(local_id, 'Repartidor')
        
        if not repartidores_disponibles:
            raise Exception('No hay repartidores disponibles en este momento')
        
        # Si buscar_empleado_disponible retorna un solo empleado, convertir a lista
        if not isinstance(repartidores_disponibles, list):
            repartidores_disponibles = [repartidores_disponibles]
        
        # Intentar asignar cada repartidor en orden de calificación
        ultimo_error = None
        for candidato in repartidores_disponibles:
            try:
                # Intentar marcar como ocupado
                marcar_empleado_ocupado(local_id, candidato['dni'])
                repartidor = candidato
                print(f'Repartidor {candidato["dni"]} asignado exitosamente')
                break
            except Exception as e:
                print(f'Error asignando repartidor {candidato["dni"]}: {str(e)}. Intentando con siguiente...')
                ultimo_error = e
                continue
        
        # Si ningún repartidor pudo ser asignado
        if not repartidor:
            raise Exception(f'No se pudo asignar ningún repartidor disponible. Último error: {str(ultimo_error)}')
        
        # Actualizar estado del pedido (esto liberará automáticamente al despachador)
        pedido_actualizado = actualizar_estado_pedido_con_empleado(
            local_id,
            pedido_id,
            'enviando',
            repartidor
        )
        
        # Liberar al despachador explícitamente si hay uno
        empleado_anterior_dni = pedido_actualizado.get('_empleado_anterior_dni')
        if empleado_anterior_dni:
            marcar_empleado_libre(local_id, empleado_anterior_dni)
            print(f'Despachador {empleado_anterior_dni} liberado')
        
        print(f"Pedido asignado a repartidor {repartidor['dni']}")
        
        result = {
            'local_id': local_id,
            'pedido_id': pedido_id,
            'usuario_correo': pedido.get('usuario_correo'),
            'repartidor_dni': repartidor['dni'],
            'estado': 'enviando',
            'historial_estados': pedido_actualizado.get('historial_estados', pedido.get('historial_estados', []))
        }

        # Enviar notificación WebSocket
        enviar_notificacion_pedido(
            pedido_id=pedido_id,
            usuario_correo=event.get('usuario_correo'),
            tipo_evento='ESTADO_CAMBIADO',
            datos={
                'estado': 'enviando',
                'empleado': {
                    'dni': repartidor['dni'],
                    'nombre': repartidor.get('nombre', ''),
                    'role': 'Repartidor'
                },
                'mensaje': f'¡Tu pedido está en camino! {repartidor.get("nombre", "un repartidor")} lo está entregando'
            }
        )
        
        if 'body' in event:
            return {
                'statusCode': 200,
                'body': json_dumps(result),
                'headers': {'Content-Type': 'application/json'}
            }
        
        return result
        
    except Exception as e:
        print(f'Error en lambda enviar: {str(e)}')
        
        if 'body' in event:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)}),
                'headers': {'Content-Type': 'application/json'}
            }
        raise