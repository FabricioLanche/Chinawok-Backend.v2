import os, json, boto3, logging
from utils.cors_utils import get_cors_headers  # <-- importar CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dynamodb = boto3.resource('dynamodb')
table_locales = dynamodb.Table(os.environ.get('TABLE_LOCALES', 'ChinaWok-Locales'))
table_usuarios = dynamodb.Table(os.environ.get('TABLE_USUARIOS', 'ChinaWok-Usuarios'))

def lambda_handler(event, context):
    headers = get_cors_headers()  # <-- CORS headers

    # Manejar preflight request
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"message": "CORS preflight successful"})
        }

    try:
        local_id = event.get('pathParameters', {}).get('local_id')
        if not local_id:
            return _resp(400, {"message": "Falta el parámetro 'local_id' en el path"}, headers)
        
        logger.info(f"Eliminando local con local_id: {local_id}")
        
        # Primero obtener el local para conocer el gerente
        try:
            local_resp = table_locales.get_item(Key={"local_id": local_id})
            local = local_resp.get("Item")
            
            if not local:
                return _resp(404, {"message": f"Local con id '{local_id}' no encontrado"}, headers)
            
            # Obtener el correo del gerente
            gerente = local.get("gerente", {})
            correo_gerente = gerente.get("correo")
            
            if correo_gerente:
                logger.info(f"Cambiando rol del gerente {correo_gerente} de Gerente a Cliente")
                table_usuarios.update_item(
                    Key={"correo": correo_gerente},
                    UpdateExpression="SET #role = :new_role",
                    ExpressionAttributeNames={"#role": "role"},
                    ExpressionAttributeValues={":new_role": "Cliente"}
                )
        except Exception as e:
            logger.error(f"Error al actualizar rol del gerente: {str(e)}")
            # Continuar con la eliminación aunque falle la actualización del usuario
        
        # Eliminar el local
        table_locales.delete_item(Key={"local_id": local_id})
        return _resp(200, {"message": "Local eliminado y gerente actualizado a Cliente"}, headers)
        
    except Exception as e:
        logger.exception(f"Error al eliminar local: {str(e)}")
        return _resp(500, {"message": "Error al eliminar el local", "error": str(e)}, headers)

def _resp(status, body, headers):
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body, ensure_ascii=False)
    }
