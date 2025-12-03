import json
import boto3
import os
from botocore.exceptions import ClientError
from decimal import Decimal
from utils.cors_utils import get_cors_headers  # <-- agregado

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_PEDIDOS', 'ChinaWok-Pedidos')
table = dynamodb.Table(table_name)

# Tabla de productos
productos_table_name = os.environ.get('TABLE_PRODUCTOS', 'ChinaWok-Productos')
productos_table = dynamodb.Table(productos_table_name)

# Tabla de combos
combos_table_name = os.environ.get('TABLE_COMBOS', 'ChinaWok-Combos')
combos_table = dynamodb.Table(combos_table_name)

# Tabla de locales
locales_table_name = os.environ.get('TABLE_LOCALES', 'ChinaWok-Locales')
locales_table = dynamodb.Table(locales_table_name)

# Tabla de usuarios
usuarios_table_name = os.environ.get('TABLE_USUARIOS', 'ChinaWok-Usuarios')
usuarios_table = dynamodb.Table(usuarios_table_name)

# Tabla de empleados
empleados_table_name = os.environ.get('TABLE_EMPLEADOS', 'ChinaWok-Empleados')
empleados_table = dynamodb.Table(empleados_table_name)

# Schema de validación (sin requerir todas las propiedades para update parcial)
PEDIDO_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "PedidosUpdate",
    "type": "object",
    "properties": {
        "productos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "cantidad": {"type": "integer", "minimum": 1}
                },
                "required": ["nombre", "cantidad"],
                "additionalProperties": False
            },
            "minItems": 1
        },
        "combos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "combo_id": {"type": "string"},
                    "cantidad": {"type": "integer", "minimum": 1}
                },
                "required": ["combo_id", "cantidad"],
                "additionalProperties": False
            },
            "minItems": 1
        },
        "costo": {"type": "number", "minimum": 0},
        "direccion": {"type": "string"},
        "fecha_entrega_aproximada": {
            "type": ["string", "null"],
            "format": "date-time"
        },
        "estado": {
            "type": "string",
            "enum": ["procesando", "cocinando", "empacando", "enviando", "recibido"]
        },
        "historial_estados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "estado": {
                        "type": "string",
                        "enum": ["procesando", "cocinando", "empacando", "enviando", "recibido"]
                    },
                    "hora_inicio": {"type": "string", "format": "date-time"},
                    "hora_fin": {"type": "string", "format": "date-time"},
                    "activo": {"type": "boolean"},
                    "empleado": {
                        "type": ["object", "null"],
                        "properties": {
                            "dni": {"type": "string"}
                        },
                        "required": ["dni"]
                    }
                },
                "required": ["estado", "hora_inicio", "hora_fin", "activo"]
            },
            "minItems": 1
        }
    },
    "additionalProperties": False,
    "minProperties": 1
}


def verificar_local_existe(local_id):
    """
    Verifica que el local exista
    Returns: (bool, str) - (éxito, mensaje de error)
    """
    try:
        response = locales_table.get_item(
            Key={'local_id': local_id}
        )
        
        if 'Item' not in response:
            return False, f"El local '{local_id}' no existe"
        
        return True, None
        
    except ClientError as e:
        return False, f"Error al verificar local: {str(e)}"


def verificar_usuario_info_bancaria(usuario_correo):
    """
    Verifica que el usuario exista y tenga información bancaria completa
    Returns: (bool, str) - (éxito, mensaje de error)
    """
    try:
        response = usuarios_table.get_item(
            Key={'correo': usuario_correo}
        )
        
        if 'Item' not in response:
            return False, f"El usuario '{usuario_correo}' no existe"
        
        usuario = response['Item']
        info_bancaria = usuario.get('informacion_bancaria')
        
        if not info_bancaria:
            return False, f"El usuario '{usuario_correo}' no tiene información bancaria registrada"
        
        # Verificar que todos los campos requeridos estén presentes y no sean None/vacíos
        campos_requeridos = ['numero_tarjeta', 'cvv', 'fecha_vencimiento', 'direccion_delivery']
        for campo in campos_requeridos:
            if not info_bancaria.get(campo):
                return False, f"El usuario '{usuario_correo}' tiene información bancaria incompleta (falta: {campo})"
        
        return True, None
        
    except ClientError as e:
        return False, f"Error al verificar usuario: {str(e)}"


def verificar_productos_stock(local_id, productos):
    """
    Verifica que los productos existan en el local y tengan stock suficiente
    Returns: (bool, str) - (éxito, mensaje de error)
    """
    for producto in productos:
        nombre = producto['nombre']
        cantidad = producto['cantidad']
        
        try:
            # Obtener producto de DynamoDB
            response = productos_table.get_item(
                Key={
                    'local_id': local_id,
                    'nombre': nombre
                }
            )
            
            if 'Item' not in response:
                return False, f"El producto '{nombre}' no existe en el local {local_id}"
            
            producto_db = response['Item']
            stock_disponible = producto_db.get('stock', 0)
            
            if stock_disponible < cantidad:
                return False, f"Stock insuficiente para '{nombre}'. Disponible: {stock_disponible}, Solicitado: {cantidad}"
                
        except ClientError as e:
            return False, f"Error al verificar producto '{nombre}': {str(e)}"
    
    return True, None


def verificar_combos(local_id, combos):
    """
    Verifica que los combos existan
    Returns: (bool, str) - (éxito, mensaje de error)
    """
    for combo in combos:
        combo_id = combo['combo_id']
        
        try:
            # Obtener combo de DynamoDB
            response = combos_table.get_item(
                Key={
                    'local_id': local_id,
                    'combo_id': combo_id
                }
            )
            
            if 'Item' not in response:
                return False, f"El combo '{combo_id}' no existe en el local {local_id}"
                
        except ClientError as e:
            return False, f"Error al verificar combo '{combo_id}': {str(e)}"
    
    return True, None


def enriquecer_empleados_historial(local_id, historial_estados):
    """
    Completa la información de los empleados en el historial consultando la BD.
    Solo requiere el DNI en el request, el resto se obtiene de la BD.
    Returns: (historial_enriquecido, error_msg) - (historial completo o None, mensaje de error o None)
    """
    historial_enriquecido = []
    
    for estado_item in historial_estados:
        # Hacer una copia del estado actual
        estado_enriquecido = dict(estado_item)
        empleado = estado_item.get('empleado')
        
        # Si el empleado es None o null, mantenerlo así
        if not empleado:
            historial_enriquecido.append(estado_enriquecido)
            continue
        
        dni = empleado.get('dni')
        if not dni:
            historial_enriquecido.append(estado_enriquecido)
            continue
        
        try:
            # Obtener empleado completo de DynamoDB
            response = empleados_table.get_item(
                Key={
                    'local_id': local_id,
                    'dni': dni
                }
            )
            
            if 'Item' not in response:
                return None, f"El empleado con DNI '{dni}' no existe en el local {local_id}"
            
            empleado_db = response['Item']
            
            # Construir objeto empleado completo desde la BD
            # El esquema de empleados tiene 'nombre', 'apellido' y 'role' (no 'rol')
            nombre = empleado_db.get('nombre', '')
            apellido = empleado_db.get('apellido', '')
            nombre_completo = f"{nombre} {apellido}".strip()
            
            # Mapear 'role' de BD a 'rol' para el pedido (y convertir a minúsculas)
            role_bd = empleado_db.get('role', '')
            rol_pedido = role_bd.lower() if role_bd else ''
            
            estado_enriquecido['empleado'] = {
                'dni': dni,
                'nombre_completo': nombre_completo,
                'rol': rol_pedido,
                'calificacion_prom': float(empleado_db.get('calificacion_prom', 0))
            }
            
            historial_enriquecido.append(estado_enriquecido)
                
        except ClientError as e:
            return None, f"Error al obtener empleado '{dni}': {str(e)}"
        except (ValueError, TypeError) as e:
            return None, f"Error al procesar datos del empleado '{dni}': {str(e)}"
    
    return historial_enriquecido, None


def convertir_floats_a_decimal(obj):
    """
    Convierte recursivamente todos los floats a Decimal para DynamoDB
    """
    if isinstance(obj, list):
        return [convertir_floats_a_decimal(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convertir_floats_a_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


def convertir_decimal_a_float(obj):
    """
    Convierte recursivamente todos los Decimal a float para serialización JSON
    """
    if isinstance(obj, list):
        return [convertir_decimal_a_float(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convertir_decimal_a_float(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj


def handler(event, context):
    """
    Lambda handler para actualizar un pedido en DynamoDB
    """
    cors_headers = get_cors_headers()

    try:
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)

        local_id = body.get('local_id')
        pedido_id = body.get('pedido_id')

        if not local_id or not pedido_id:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Se requieren local_id y pedido_id'})
            }

        update_data = {k: v for k, v in body.items() if k not in ['local_id', 'pedido_id', 'usuario_correo']}

        if not update_data:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'No se proporcionaron campos para actualizar'})
            }

        if 'productos' in update_data:
            if not isinstance(update_data['productos'], list) or len(update_data['productos']) == 0:
                return {
                    'statusCode': 400,
                    'headers': cors_headers,
                    'body': json.dumps({'error': 'productos debe ser un array no vacío'})
                }

        if 'combos' in update_data:
            if not isinstance(update_data['combos'], list) or len(update_data['combos']) == 0:
                return {
                    'statusCode': 400,
                    'headers': cors_headers,
                    'body': json.dumps({'error': 'combos debe ser un array no vacío'})
                }

        if 'estado' in update_data:
            estados_validos = ['procesando', 'cocinando', 'empacando', 'enviando', 'recibido']
            if update_data['estado'] not in estados_validos:
                return {
                    'statusCode': 400,
                    'headers': cors_headers,
                    'body': json.dumps({'error': f'estado debe ser uno de: {", ".join(estados_validos)}'})
                }

        try:
            pedido_actual = table.get_item(
                Key={'local_id': local_id, 'pedido_id': pedido_id}
            )

            if 'Item' not in pedido_actual:
                return {
                    'statusCode': 404,
                    'headers': cors_headers,
                    'body': json.dumps({'error': 'Pedido no encontrado'})
                }

            pedido = pedido_actual['Item']
            usuario_correo = pedido.get('usuario_correo')

        except ClientError as e:
            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Error al obtener pedido', 'message': str(e)})
            }

        exito, error_msg = verificar_local_existe(local_id)
        if not exito:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Error de validación de local', 'message': error_msg})
            }

        exito, error_msg = verificar_usuario_info_bancaria(usuario_correo)
        if not exito:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Error de validación de usuario', 'message': error_msg})
            }

        if 'productos' in update_data and update_data['productos']:
            exito, error_msg = verificar_productos_stock(local_id, update_data['productos'])
            if not exito:
                return {
                    'statusCode': 400,
                    'headers': cors_headers,
                    'body': json.dumps({'error': 'Error de validación de productos', 'message': error_msg})
                }

        if 'combos' in update_data and update_data['combos']:
            exito, error_msg = verificar_combos(local_id, update_data['combos'])
            if not exito:
                return {
                    'statusCode': 400,
                    'headers': cors_headers,
                    'body': json.dumps({'error': 'Error de validación de combos', 'message': error_msg})
                }

        if 'historial_estados' in update_data and update_data['historial_estados']:
            historial_enriquecido, error_msg = enriquecer_empleados_historial(local_id, update_data['historial_estados'])
            if historial_enriquecido is None:
                return {
                    'statusCode': 400,
                    'headers': cors_headers,
                    'body': json.dumps({
                        'error': 'Error al enriquecer datos de empleados',
                        'message': error_msg
                    })
                }
            update_data['historial_estados'] = historial_enriquecido

        update_data = convertir_floats_a_decimal(update_data)

        update_expression = "SET " + ", ".join([f"#{k} = :{k}" for k in update_data.keys()])
        expression_attribute_names = {f"#{k}": k for k in update_data.keys()}
        expression_attribute_values = {f":{k}": v for k, v in update_data.items()}

        response = table.update_item(
            Key={'local_id': local_id, 'pedido_id': pedido_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="ALL_NEW"
        )

        data_respuesta = convertir_decimal_a_float(response['Attributes'])

        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({'message': 'Pedido actualizado exitosamente', 'data': data_respuesta})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': 'Error interno del servidor', 'message': str(e)})
        }
