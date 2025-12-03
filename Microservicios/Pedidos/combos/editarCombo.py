import json
import boto3
import os
from utils.cors_utils import get_cors_headers   # <-- CORS uniforme

# Cliente DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_COMBOS', 'ChinaWok-Combos')
table = dynamodb.Table(table_name)


def handler(event, context):
    """
    Lambda handler para actualizar un combo en DynamoDB
    """
    try:
        # Parseo de body con estándar del login
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", event)
        
        # Obtener las keys
        local_id = body.get('local_id')
        combo_id = body.get('combo_id')
        
        if not local_id or not combo_id:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'Se requieren local_id y combo_id'
                })
            }
        
        # Solo campos permitidos
        campos_permitidos = ['nombre', 'productos_nombres', 'descripcion']
        update_data = {k: v for k, v in body.items() if k in campos_permitidos}
        
        if not update_data:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'error': 'No se proporcionaron campos para actualizar'
                })
            }
        
        # Validación especial de productos_nombres
        if 'productos_nombres' in update_data:
            if not isinstance(update_data['productos_nombres'], list) or len(update_data['productos_nombres']) == 0:
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({
                        'error': 'productos_nombres debe ser un array con al menos un elemento'
                    })
                }
        
        # Expresión de actualización
        update_expression = "SET " + ", ".join([f"#{k} = :{k}" for k in update_data.keys()])
        expression_attribute_names = {f"#{k}": k for k in update_data.keys()}
        expression_attribute_values = {f":{k}": v for k, v in update_data.items()}
        
        # Actualizar en DynamoDB
        response = table.update_item(
            Key={
                'local_id': local_id,
                'combo_id': combo_id
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="ALL_NEW"
        )
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'message': 'Combo actualizado exitosamente',
                'data': response['Attributes']
            }, default=str)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'error': 'Error interno del servidor',
                'message': str(e)
            })
        }
