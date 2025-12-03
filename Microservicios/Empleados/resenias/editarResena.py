import boto3, json, os
from decimal import Decimal
from utils.cors_utils import get_cors_headers  # <-- CORS

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_RESENAS'])

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
        local_id = event['pathParameters']['local_id']
        resena_id = event['pathParameters']['resena_id']
        body = json.loads(event['body'])

        update_expr = []
        expr_vals = {}
        for k, v in body.items():
            if k not in ['resena', 'calificacion']:
                continue
            if k == 'calificacion':
                # Convertir a Decimal para DynamoDB
                v = Decimal(str(v))
                if not (Decimal('0') <= v <= Decimal('5')):
                    return {
                        'statusCode': 400,
                        'headers': headers,
                        'body': json.dumps({'error': 'Calificación fuera de rango'})
                    }
            update_expr.append(f"{k} = :{k}")
            expr_vals[f":{k}"] = v

        if not update_expr:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'No hay campos válidos para actualizar'})
            }

        response = table.update_item(
            Key={'local_id': local_id, 'resena_id': resena_id},
            UpdateExpression="SET " + ", ".join(update_expr),
            ExpressionAttributeValues=expr_vals,
            ReturnValues='ALL_NEW'
        )

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'Reseña actualizada', 'resena': response['Attributes']}, cls=DecimalEncoder)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f"Error al actualizar reseña: {str(e)}"})
        }
