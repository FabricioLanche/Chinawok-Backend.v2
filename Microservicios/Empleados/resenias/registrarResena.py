import boto3, json, uuid, os
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from utils.cors_utils import get_cors_headers  # <-- importar CORS

dynamodb = boto3.resource('dynamodb')
tabla_resenas = dynamodb.Table(os.environ['TABLE_RESENAS'])
tabla_locales = dynamodb.Table(os.environ['TABLE_LOCALES'])
tabla_pedidos = dynamodb.Table(os.environ['TABLE_PEDIDOS'])

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    headers = get_cors_headers()  # <-- aplicar CORS

    # Manejar preflight request
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'CORS preflight successful'})
        }

    try:
        body = json.loads(event['body'])
        required = ['local_id', 'pedido_id', 'calificacion']

        for field in required:
            if field not in body:
                return {'statusCode': 400, 'headers': headers,
                        'body': json.dumps({'error': f"Falta el campo {field}"})}

        local_id = body['local_id']
        pedido_id = body['pedido_id']

        # Validar que el local existe
        response_local = tabla_locales.get_item(Key={'local_id': local_id})
        if 'Item' not in response_local:
            return {'statusCode': 404, 'headers': headers,
                    'body': json.dumps({'error': f"Local {local_id} no encontrado"})}

        # Validar que el pedido existe y obtener empleados del historial
        response_pedido = tabla_pedidos.get_item(Key={'local_id': local_id, 'pedido_id': pedido_id})
        if 'Item' not in response_pedido:
            return {'statusCode': 404, 'headers': headers,
                    'body': json.dumps({'error': f"Pedido {pedido_id} no encontrado"})}

        pedido = response_pedido['Item']

        # Extraer DNIs de empleados del historial de estados
        historial_estados = pedido.get('historial_estados', [])
        cocinero_dni = despachador_dni = repartidor_dni = None

        for estado in historial_estados:
            empleado = estado.get('empleado')
            if empleado:
                rol = empleado.get('rol', '').lower()
                dni = empleado.get('dni')
                if dni:
                    if rol == 'cocinero' and not cocinero_dni:
                        cocinero_dni = dni
                    elif rol == 'despachador' and not despachador_dni:
                        despachador_dni = dni
                    elif rol == 'repartidor' and not repartidor_dni:
                        repartidor_dni = dni

        if not cocinero_dni or not despachador_dni or not repartidor_dni:
            return {
                'statusCode': 400, 'headers': headers,
                'body': json.dumps({
                    'error': 'No se encontraron todos los empleados requeridos en el historial del pedido',
                    'encontrados': {
                        'cocinero_dni': cocinero_dni,
                        'despachador_dni': despachador_dni,
                        'repartidor_dni': repartidor_dni
                    }
                })
            }

        # Convertir calificacion a Decimal para DynamoDB
        calificacion = Decimal(str(body['calificacion']))
        if not (Decimal('0') <= calificacion <= Decimal('5')):
            return {'statusCode': 400, 'headers': headers,
                    'body': json.dumps({'error': 'La calificación debe estar entre 0 y 5'})}

        # Crear el item de reseña único
        resena_id = str(uuid.uuid4())
        item = {
            'local_id': local_id,
            'resena_id': resena_id,
            'pedido_id': pedido_id,
            'cocinero_dni': cocinero_dni,
            'despachador_dni': despachador_dni,
            'repartidor_dni': repartidor_dni,
            'resena': body.get('resena', ''),
            'calificacion': calificacion
        }

        tabla_resenas.put_item(Item=item)

        return {
            'statusCode': 201,
            'headers': headers,
            'body': json.dumps({'message': 'Reseña registrada exitosamente', 'resena': item}, cls=DecimalEncoder)
        }

    except Exception as e:
        return {'statusCode': 500, 'headers': headers,
                'body': json.dumps({'error': f"Error al registrar reseña: {str(e)}"})}
