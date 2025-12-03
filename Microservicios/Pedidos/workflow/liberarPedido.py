import json
import boto3
import os
from datetime import datetime, timezone
from utils.dynamodb_helper import (
    obtener_pedido,
    marcar_empleado_libre,
    resetear_pedido_a_inicial
)

def lambda_handler(event, context):
    """Lambda para liberar todos los empleados asignados a un pedido"""
    print(f'Liberando empleados del pedido: {json.dumps(event)}')
    
    local_id = event.get('local_id')
    pedido_id = event.get('pedido_id')
    motivo = event.get('motivo', 'error_workflow')
    resetear_estado = event.get('resetear_estado', True)
    
    if not local_id or not pedido_id:
        print('Faltan parámetros, no se puede liberar empleados')
        return {'liberados': 0}
    
    try:
        # Obtener el pedido para ver qué empleados están asignados
        pedido = obtener_pedido(local_id, pedido_id)
        historial = pedido.get('historial_estados', [])
        
        empleados_liberados = []
        
        # Buscar en el historial TODOS los empleados (activos o no)
        # para asegurar que liberamos a todos
        empleados_vistos = set()
        
        for estado in historial:
            if estado.get('empleado'):
                empleado_dni = estado['empleado'].get('dni')
                empleado_rol = estado['empleado'].get('rol')
                
                # Evitar liberar el mismo empleado dos veces
                if empleado_dni in empleados_vistos:
                    continue
                    
                empleados_vistos.add(empleado_dni)
                
                try:
                    marcar_empleado_libre(local_id, empleado_dni)
                    empleados_liberados.append({
                        'dni': empleado_dni,
                        'rol': empleado_rol,
                        'estaba_activo': estado.get('activo', False)
                    })
                    print(f'Empleado {empleado_rol} {empleado_dni} liberado por {motivo}')
                except Exception as e:
                    print(f'Error liberando empleado {empleado_dni}: {str(e)}')
        
        # Actualizar el estado del pedido
        try:
            pedidos_table_name = os.environ.get('TABLE_PEDIDOS', 'ChinaWok-Pedidos')
            dynamodb = boto3.resource('dynamodb')
            pedidos_table = dynamodb.Table(pedidos_table_name)
            
            ahora_iso = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
            nuevo_historial = []
            
            # Cerrar todas las entradas activas del historial
            for estado in historial:
                estado_n = dict(estado)
                if estado_n.get('activo'):
                    estado_n['activo'] = False
                    if not estado_n.get('hora_fin'):
                        estado_n['hora_fin'] = ahora_iso
                nuevo_historial.append(estado_n)
            
            # Si es por servicio saturado o reintento, marcar como cancelado
            # Si no, solo cerrar el historial sin cambiar estado
            if motivo in ['servicio_saturado', 'reintento_workflow']:
                update_expr = "SET #estado = :estado, historial_estados = :hist REMOVE task_token, esperando_confirmacion"
                estado_final = 'cancelado'
            else:
                update_expr = "SET historial_estados = :hist REMOVE task_token, esperando_confirmacion"
                estado_final = pedido.get('estado', 'procesando')
            
            pedidos_table.update_item(
                Key={'local_id': local_id, 'pedido_id': pedido_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames={'#estado': 'estado'} if motivo in ['servicio_saturado', 'reintento_workflow'] else None,
                ExpressionAttributeValues={
                    ':estado': estado_final,
                    ':hist': nuevo_historial
                } if motivo in ['servicio_saturado', 'reintento_workflow'] else {
                    ':hist': nuevo_historial
                }
            )
            print(f"Pedido {pedido_id} actualizado - estado: {estado_final}, historial cerrado")
        except Exception as e:
            print(f"Error actualizando estado del pedido: {str(e)}")
        
        # Resetear el pedido a estado inicial solo si se solicita Y no es servicio saturado
        if resetear_estado and motivo != 'servicio_saturado':
            try:
                resetear_pedido_a_inicial(local_id, pedido_id)
                print(f'Pedido {pedido_id} reseteado a estado "procesando"')
            except Exception as e:
                print(f'Error reseteando estado del pedido: {str(e)}')
        
        print(f'Total empleados liberados: {len(empleados_liberados)}')
        
        return {
            'liberados': len(empleados_liberados),
            'empleados': empleados_liberados,
            'pedido_cancelado': motivo in ['servicio_saturado', 'reintento_workflow'],
            'pedido_reseteado': resetear_estado and motivo != 'servicio_saturado',
            'motivo': motivo
        }
        
    except Exception as e:
        print(f'Error al liberar empleados: {str(e)}')
        import traceback
        print(f'Traceback: {traceback.format_exc()}')
        return {'liberados': 0, 'error': str(e)}