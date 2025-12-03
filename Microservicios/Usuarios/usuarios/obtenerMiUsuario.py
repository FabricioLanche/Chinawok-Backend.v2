import json
import boto3
import os
from utils.jwt_utils import verificar_rol
from utils.cors_utils import get_cors_headers

TABLE_USUARIOS_NAME = os.getenv("TABLE_USUARIOS", "ChinaWok-Usuarios")

dynamodb = boto3.resource("dynamodb")
usuarios_table = dynamodb.Table(TABLE_USUARIOS_NAME)


def lambda_handler(event, context):
    # Obtener usuario autenticado (del authorizer)
    authorizer = event.get("requestContext", {}).get("authorizer", {})
    correo_autenticado = authorizer.get("correo")
    if not correo_autenticado:
        return {"statusCode": 401, "body": json.dumps({"message": "No autenticado"})}

    # Si se pasa pathParameters con otro correo, indicar usar GET /usuarios/{correo}
    path_params = event.get("pathParameters") or {}
    if path_params.get("correo") and path_params.get("correo") != "me":
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Para obtener otro usuario usa GET /usuarios/{correo}"})
        }

    # Obtener info del propio usuario
    try:
        resp = usuarios_table.get_item(Key={"correo": correo_autenticado})
        if "Item" not in resp:
            return {"statusCode": 404, "body": json.dumps({"message": "Usuario no encontrado"})}
        usuario = resp["Item"]
        if "contrasena" in usuario:
            del usuario["contrasena"]
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "Usuario encontrado", "usuario": usuario}, default=str)
        }
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Error al buscar usuario: {str(e)}"})}
