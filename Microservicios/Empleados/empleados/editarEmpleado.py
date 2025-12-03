import boto3, json, os
from decimal import Decimal
from utils.cors_utils import get_cors_headers  # <-- importado

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_EMPLEADOS'])

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

    local_id = event['pathParameters']['local_id']
    dni = event['pathParameters']['dni']
    body = json.loads(event['body'])

    update_expr = []
    expr_attr_vals = {}

    for key, value in body.items():
        if key not in ['nombre', 'apellido', 'calificacion_prom', 'sueldo', 'role']:
            continue
        # Convertir campos numéricos a Decimal
        if key in ['calificacion_prom', 'sueldo']:
            value = Decimal(str(value))
            # Validar rangos
            if key == 'calificacion_prom' and not (Decimal('0') <= value <= Decimal('5')):
                return {
                    'statusCode': 400,
                    'headers': cors_headers,  # <-- reemplazado
                    'body': json.dumps({'error': 'La calificación debe estar entre 0 y 5'})
                }
            if key == 'sueldo' and value < 0:
                return {
                    'statusCode': 400,
                    'headers': cors_headers,  # <-- reemplazado
                    'body': json.dumps({'error': 'El sueldo no puede ser negativo'})
                }
        update_expr.append(f"{key} = :{key}")
        expr_attr_vals[f":{key}"] = value

    if not update_expr:
        return {
            'statusCode': 400,
            'headers': cors_headers,  # <-- reemplazado
            'body': json.dumps({'error': 'No hay campos válidos para actualizar'})
        }

    response = table.update_item(
        Key={'local_id': local_id, 'dni': dni},
        UpdateExpression="SET " + ", ".join(update_expr),
        ExpressionAttributeValues=expr_attr_vals,
        ReturnValues='ALL_NEW'
    )

    return {
        'statusCode': 200,
        'headers': cors_headers,  # <-- reemplazado
        'body': json.dumps({'message': 'Empleado actualizado', 'empleado': response['Attributes']}, cls=DecimalEncoder)
    }
