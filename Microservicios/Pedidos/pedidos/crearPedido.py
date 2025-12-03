import json
import boto3
import os
import uuid
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from decimal import Decimal
from utils.cors_utils import get_cors_headers

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

# EventBridge
eventbridge = boto3.client('events')
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'chinawok-pedidos-events')


def verificar_local_existe(local_id):
    try:
        response = locales_table.get_item(Key={'local_id': local_id})
        if 'Item' not in response:
            return False, f"El local '{local_id}' no existe"
        return True, None
    except ClientError as e:
        return False, f"Error al verificar local: {str(e)}"


def verificar_usuario_info_bancaria(usuario_correo):
    try:
        response = usuarios_table.get_item(Key={'correo': usuario_correo})
        if 'Item' not in response:
            return False, f"El usuario '{usuario_correo}' no existe"

        usuario = response['Item']
        info_bancaria = usuario.get('informacion_bancaria')

        if not info_bancaria:
            return False, f"El usuario '{usuario_correo}' no tiene información bancaria registrada"

        campos_requeridos = ['numero_tarjeta', 'cvv', 'fecha_vencimiento', 'direccion_delivery']
        for campo in campos_requeridos:
            if not info_bancaria.get(campo):
                return False, f"Información bancaria incompleta (falta: {campo})"

        return True, None

    except ClientError as e:
        return False, f"Error al verificar usuario: {str(e)}"


def verificar_productos_stock(local_id, productos):
    for producto in productos:
        nombre = producto['nombre']
        cantidad = producto['cantidad']

        try:
            response = productos_table.get_item(
                Key={'local_id': local_id, 'nombre': nombre}
            )

            if 'Item' not in response:
                return False, f"El producto '{nombre}' no existe en el local {local_id}"

            stock_disponible = response['Item'].get('stock', 0)

            if stock_disponible < cantidad:
                return False, f"Stock insuficiente para '{nombre}'"

        except ClientError as e:
            return False, f"Error al verificar producto '{nombre}': {str(e)}"

    return True, None


def verificar_combos(local_id, combos):
    for combo in combos:
        combo_id = combo['combo_id']

        try:
            response = combos_table.get_item(
                Key={'local_id': local_id, 'combo_id': combo_id}
            )

            if 'Item' not in response:
                return False, f"El combo '{combo_id}' no existe en el local {local_id}"

        except ClientError as e:
            return False, f"Error al verificar combo '{combo_id}': {str(e)}"

    return True, None


def convertir_floats_a_decimal(obj):
    if isinstance(obj, list):
        return [convertir_floats_a_decimal(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convertir_floats_a_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    return obj


def convertir_decimal_a_float(obj):
    if isinstance(obj, list):
        return [convertir_decimal_a_float(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convertir_decimal_a_float(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj


def handler(event, context):
    try:
        body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', event)

        campos_requeridos = ['local_id', 'usuario_correo', 'direccion', 'costo']
        for campo in campos_requeridos:
            if campo not in body:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'error': f'Campo requerido faltante: {campo}'})
                }

        if 'productos' not in body and 'combos' not in body:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Debe especificar productos o combos'})
            }

        # Validaciones
        if 'productos' in body:
            if not isinstance(body['productos'], list) or len(body['productos']) == 0:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'error': 'productos debe ser un array no vacío'})
                }

        if 'combos' in body:
            if not isinstance(body['combos'], list) or len(body['combos']) == 0:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'error': 'combos debe ser un array no vacío'})
                }

        if not isinstance(body['costo'], (int, float)) or body['costo'] < 0:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'costo debe ser un número positivo'})
            }

        # Identificadores y estado
        body['pedido_id'] = str(uuid.uuid4())
        hora_inicio = datetime.utcnow()
        hora_fin = hora_inicio + timedelta(seconds=2.5)

        # Asignar fecha de creación automáticamente
        body['fecha_creacion'] = hora_inicio.isoformat() + 'Z'

        body['estado'] = 'procesando'
        body['historial_estados'] = [{
            'estado': 'procesando',
            'hora_inicio': hora_inicio.isoformat() + 'Z',
            'hora_fin': hora_fin.isoformat() + 'Z',
            'activo': True,
            'empleado': None
        }]

        # Validaciones externas
        exito, err = verificar_local_existe(body['local_id'])
        if not exito:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Error validación local', 'message': err})
            }

        exito, err = verificar_usuario_info_bancaria(body['usuario_correo'])
        if not exito:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'error': 'Error validación usuario', 'message': err})
            }

        if 'productos' in body:
            exito, err = verificar_productos_stock(body['local_id'], body['productos'])
            if not exito:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'error': 'Error validación productos', 'message': err})
                }

        if 'combos' in body:
            exito, err = verificar_combos(body['local_id'], body['combos'])
            if not exito:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'error': 'Error validación combos', 'message': err})
                }

        # Guardar pedido
        body = convertir_floats_a_decimal(body)
        table.put_item(Item=body)
        
        # Actualizar historial_pedidos del usuario con {pedido_id, local_id}
        try:
            usuario_correo = body['usuario_correo']
            pedido_id = body['pedido_id']
            local_id = body['local_id']

            nuevo_registro = {
                'pedido_id': pedido_id,
                'local_id': local_id
            }
            
            usuarios_table.update_item(
                Key={'correo': usuario_correo},
                UpdateExpression='SET historial_pedidos = list_append(if_not_exists(historial_pedidos, :empty_list), :pedido)',
                ExpressionAttributeValues={
                    ':pedido': [nuevo_registro],
                    ':empty_list': []
                }
            )
        except Exception as e:
            # Log error pero no fallar la creación del pedido
            print(f"Warning: No se pudo actualizar historial de usuario: {str(e)}")

        try:
            eventbridge.put_events(Entries=[{
                'Source': 'chinawok.pedidos',
                'DetailType': 'PedidoCreado',
                'Detail': json.dumps(convertir_decimal_a_float(body)),
                'EventBusName': EVENT_BUS_NAME
            }])
        except Exception:
            pass

        return {
            'statusCode': 201,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': 'Pedido creado exitosamente', 'data': convertir_decimal_a_float(body)})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'error': 'Error interno del servidor', 'message': str(e)})
        }