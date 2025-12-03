import boto3
import os
import json
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

def obtener_pedido(local_id, pedido_id):
    """Obtiene un pedido completo de DynamoDB"""
    table = dynamodb.Table(os.environ['TABLE_PEDIDOS'])
    
    try:
        response = table.get_item(
            Key={
                'local_id': local_id,
                'pedido_id': pedido_id
            }
        )
        
        pedido = response.get('Item')
        if not pedido:
            raise Exception(f'Pedido {pedido_id} no encontrado')
        
        print(f'Pedido obtenido: {pedido_id}')
        return pedido
        
    except Exception as e:
        print(f'Error obteniendo pedido: {str(e)}')
        raise

def buscar_empleado_disponible(local_id, role):
    """Busca un empleado disponible (ocupado=False) del tipo especificado"""
    table = dynamodb.Table(os.environ['TABLE_EMPLEADOS'])
    
    try:
        print(f'Buscando {role} disponible en local {local_id}')
        
        response = table.query(
            KeyConditionExpression=Key('local_id').eq(local_id),
            FilterExpression=Attr('role').eq(role) & Attr('ocupado').eq(False)
        )
        
        empleados = response.get('Items', [])
        
        print(f'Empleados encontrados con role={role} y ocupado=False: {len(empleados)}')
        
        if not empleados:
            print(f'No se encontraron {role}s disponibles en local {local_id}')
            return None
        
        # Retornar el empleado con mejor calificación
        empleado = sorted(
            empleados, 
            key=lambda x: float(x.get('calificacion_prom', 0)), 
            reverse=True
        )[0]
        
        print(f'Empleado {role} seleccionado: {empleado["dni"]} - {empleado["nombre"]} {empleado["apellido"]} (calificación: {empleado.get("calificacion_prom")})')
        
        return empleado
        
    except Exception as e:
        print(f'Error buscando empleado: {str(e)}')
        import traceback
        print(f'Traceback: {traceback.format_exc()}')
        raise

def marcar_empleado_ocupado(local_id, dni):
    """Marca un empleado como ocupado (ocupado=True)"""
    table = dynamodb.Table(os.environ['TABLE_EMPLEADOS'])
    
    try:
        response = table.update_item(
            Key={
                'local_id': local_id,
                'dni': dni
            },
            UpdateExpression='SET ocupado = :ocupado',
            ExpressionAttributeValues={
                ':ocupado': True
            },
            ReturnValues='ALL_NEW'
        )
        
        print(f'Empleado {dni} marcado como ocupado')
        return response.get('Attributes')
        
    except Exception as e:
        print(f'Error marcando empleado como ocupado: {str(e)}')
        raise

def marcar_empleado_libre(local_id, dni):
    """Marca un empleado como libre (ocupado=False)"""
    table = dynamodb.Table(os.environ['TABLE_EMPLEADOS'])
    
    try:
        response = table.update_item(
            Key={
                'local_id': local_id,
                'dni': dni
            },
            UpdateExpression='SET ocupado = :ocupado',
            ExpressionAttributeValues={
                ':ocupado': False
            },
            ReturnValues='ALL_NEW'
        )
        
        print(f'Empleado {dni} marcado como libre')
        return response.get('Attributes')
        
    except Exception as e:
        print(f'Error marcando empleado como libre: {str(e)}')
        raise

# Orden de estados válido
ESTADOS_ORDEN = ['procesando', 'cocinando', 'empacando', 'enviando', 'recibido']

def validar_transicion_estado(estado_actual, estado_nuevo):
    """Valida que la transición de estado sea válida (solo al siguiente estado)"""
    try:
        indice_actual = ESTADOS_ORDEN.index(estado_actual)
        indice_nuevo = ESTADOS_ORDEN.index(estado_nuevo)
        
        # Solo permitir avanzar al siguiente estado
        if indice_nuevo != indice_actual + 1:
            raise ValueError(
                f'Transición inválida: no se puede pasar de "{estado_actual}" a "{estado_nuevo}". '
                f'El siguiente estado válido es "{ESTADOS_ORDEN[indice_actual + 1]}"'
            )
        
        return True
        
    except ValueError as e:
        print(f'Error en validación de estado: {str(e)}')
        raise

def actualizar_estado_pedido_con_empleado(local_id, pedido_id, nuevo_estado, empleado):
    """Actualiza el estado de un pedido agregando nuevo historial con empleado"""
    table = dynamodb.Table(os.environ['TABLE_PEDIDOS'])
    
    try:
        ahora = datetime.now().isoformat()
        
        # Obtener el pedido actual para validar y actualizar el historial
        pedido = obtener_pedido(local_id, pedido_id)
        estado_actual = pedido.get('estado')
        
        # Validar que la transición sea válida
        validar_transicion_estado(estado_actual, nuevo_estado)
        
        historial_actual = pedido.get('historial_estados', [])
        
        # Cerrar el estado activo anterior y extraer DNI del empleado anterior
        empleado_anterior_dni = None
        for estado in historial_actual:
            if estado.get('activo', False):
                estado['activo'] = False
                estado['hora_fin'] = ahora
                # Extraer DNI del empleado que estaba en el estado anterior
                if estado.get('empleado'):
                    empleado_anterior_dni = estado['empleado'].get('dni')
        
        # Crear nuevo estado
        nuevo_historial = {
            'estado': nuevo_estado,
            'hora_inicio': ahora,
            'hora_fin': ahora,
            'activo': True
        }
        
        if empleado:
            # Convertir float a Decimal para DynamoDB
            calificacion = empleado.get('calificacion_prom', 0)
            if isinstance(calificacion, float):
                calificacion = Decimal(str(calificacion))
            elif isinstance(calificacion, str):
                calificacion = Decimal(calificacion)
            
            nuevo_historial['empleado'] = {
                'dni': empleado['dni'],
                'nombre_completo': f"{empleado['nombre']} {empleado['apellido']}",
                'rol': empleado['role'].lower(),
                'calificacion_prom': calificacion
            }
        
        historial_actual.append(nuevo_historial)
        
        # Actualizar pedido
        response = table.update_item(
            Key={
                'local_id': local_id,
                'pedido_id': pedido_id
            },
            UpdateExpression='SET estado = :estado, historial_estados = :historial',
            ExpressionAttributeValues={
                ':estado': nuevo_estado,
                ':historial': historial_actual
            },
            ReturnValues='ALL_NEW'
        )
        
        print(f'Pedido {pedido_id} actualizado de "{estado_actual}" a "{nuevo_estado}"')
        
        # Retornar también el DNI del empleado anterior para liberarlo
        result = response.get('Attributes')
        result['_empleado_anterior_dni'] = empleado_anterior_dni
        
        return result
        
    except Exception as e:
        print(f'Error actualizando estado del pedido: {str(e)}')
        raise

def finalizar_pedido(local_id, pedido_id):
    """Finaliza el pedido marcando el último estado como inactivo"""
    table = dynamodb.Table(os.environ['TABLE_PEDIDOS'])
    
    try:
        ahora = datetime.now().isoformat()
        
        pedido = obtener_pedido(local_id, pedido_id)
        historial_actual = pedido.get('historial_estados', [])
        
        # Cerrar el último estado activo
        for estado in historial_actual:
            if estado.get('activo', False):
                estado['activo'] = False
                estado['hora_fin'] = ahora
        
        response = table.update_item(
            Key={
                'local_id': local_id,
                'pedido_id': pedido_id
            },
            UpdateExpression='SET estado = :estado, historial_estados = :historial',
            ExpressionAttributeValues={
                ':estado': 'recibido',
                ':historial': historial_actual
            },
            ReturnValues='ALL_NEW'
        )
        
        print(f'Pedido {pedido_id} finalizado')
        return response.get('Attributes')
        
    except Exception as e:
        print(f'Error finalizando pedido: {str(e)}')
        raise

def agregar_pedido_a_usuario(usuario_correo, pedido_id):
    """Agrega un pedido al historial del usuario"""
    table = dynamodb.Table(os.environ['TABLE_USUARIOS'])
    
    try:
        response = table.update_item(
            Key={'correo': usuario_correo},
            UpdateExpression='SET historial_pedidos = list_append(if_not_exists(historial_pedidos, :empty_list), :pedido)',
            ExpressionAttributeValues={
                ':pedido': [pedido_id],
                ':empty_list': []
            },
            ReturnValues='UPDATED_NEW'
        )
        
        print(f'Pedido {pedido_id} agregado al historial del usuario {usuario_correo}')
        return response.get('Attributes')
        
    except Exception as e:
        print(f'Error agregando pedido al usuario: {str(e)}')
        raise

def resetear_pedido_a_inicial(local_id, pedido_id):
    """Resetea un pedido a su estado inicial para reintentar el workflow"""
    table = dynamodb.Table(os.environ['TABLE_PEDIDOS'])
    
    try:
        ahora = datetime.now().isoformat()
        
        # Resetear a estado procesando con historial limpio
        response = table.update_item(
            Key={
                'local_id': local_id,
                'pedido_id': pedido_id
            },
            UpdateExpression='SET estado = :estado, historial_estados = :historial, REMOVE task_token, esperando_confirmacion',
            ExpressionAttributeValues={
                ':estado': 'procesando',
                ':historial': [
                    {
                        'estado': 'procesando',
                        'hora_inicio': ahora,
                        'hora_fin': ahora,
                        'activo': True,
                        'empleado': None
                    }
                ]
            },
            ReturnValues='ALL_NEW'
        )
        
        print(f'Pedido {pedido_id} reseteado a estado inicial')
        return response.get('Attributes')
        
    except Exception as e:
        print(f'Error reseteando pedido: {str(e)}')
        raise
