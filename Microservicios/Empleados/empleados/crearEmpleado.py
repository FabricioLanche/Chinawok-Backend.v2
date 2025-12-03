import boto3, json, os, re
from decimal import Decimal
from botocore.exceptions import ClientError
from utils.cors_utils import get_cors_headers  # <-- agregado

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_EMPLEADOS'])
table_locales = dynamodb.Table(os.environ['TABLE_LOCALES'])

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    cors_headers = get_cors_headers()  # <-- reemplaza headers manuales
    
    # Manejar preflight request
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({'message': 'CORS preflight successful'})
        }

    body = json.loads(event['body'])

    required = ["local_id", "dni", "nombre", "apellido", "role", "sueldo"]
    for field in required:
        if field not in body:
            return {
                'statusCode': 400,
                'headers': cors_headers,  # <-- reemplazado
                'body': json.dumps({'error': f"Falta el campo requerido: {field}"})
            }

    # Validar existencia del local
    try:
        response = table_locales.get_item(Key={'local_id': body['local_id']})
        if 'Item' not in response:
            return {
                'statusCode': 400,
                'headers': cors_headers,  # <-- reemplazado
                'body': json.dumps({'error': 'El local_id no existe en la tabla de locales'})
            }
    except ClientError as e:
        return {
            'statusCode': 500,
            'headers': cors_headers,  # <-- reemplazado
            'body': json.dumps({'error': f"Error al verificar local: {str(e)}"})
        }

    # Validar formato DNI peruano (8 dígitos numéricos)
    if not re.match(r'^\d{8}$', body['dni']):
        return {
            'statusCode': 400,
            'headers': cors_headers,  # <-- reemplazado
            'body': json.dumps({'error': 'El DNI debe tener exactamente 8 dígitos numéricos'})
        }

    # Validar rol
    roles_validos = ["Repartidor", "Cocinero", "Despachador"]
    if body['role'] not in roles_validos:
        return {
            'statusCode': 400,
            'headers': cors_headers,  # <-- reemplazado
            'body': json.dumps({'error': f"El rol debe ser uno de: {', '.join(roles_validos)}"})
        }

    # Validar sueldo
    sueldo = Decimal(str(body['sueldo']))
    if sueldo < 0:
        return {
            'statusCode': 400,
            'headers': cors_headers,  # <-- reemplazado
            'body': json.dumps({'error': 'El sueldo no puede ser negativo'})
        }

    item = {
        'local_id': body['local_id'],
        'dni': body['dni'],
        'nombre': body['nombre'],
        'apellido': body['apellido'],
        'role': body['role'],
        'calificacion_prom': Decimal('0'),
        'sueldo': sueldo,
        'ocupado': False
    }

    table.put_item(Item=item)
    return {
        'statusCode': 201,
        'headers': cors_headers,  # <-- reemplazado
        'body': json.dumps({'message': 'Empleado creado', 'empleado': item}, cls=DecimalEncoder)
    }
