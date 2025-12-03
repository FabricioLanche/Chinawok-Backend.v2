import json
import boto3
import os
from utils.authentication_utils import obtener_usuario_autenticado, validar_acceso_usuario
from utils.cors_utils import get_cors_headers

TABLE_USUARIOS_NAME = os.getenv("TABLE_USUARIOS", "ChinaWok-Usuarios")

dynamodb = boto3.resource("dynamodb")
usuarios_table = dynamodb.Table(TABLE_USUARIOS_NAME)


def lambda_handler(event, context):
    # Preferir path parameter: /usuarios/{correo}
    correo = None
    if isinstance(event, dict):
        path_params = event.get("pathParameters") or {}
        correo = path_params.get("correo")

    # Fallback a body antiguo (compatibilidad)
    if not correo:
        body = {}
        if isinstance(event, dict) and "body" in event:
            raw_body = event.get("body")
            if isinstance(raw_body, str):
                if raw_body:
                    body = json.loads(raw_body)
                else:
                    body = {}
            elif isinstance(raw_body, dict):
                body = raw_body
        elif isinstance(event, dict):
            body = event
        elif isinstance(event, str):
            body = json.loads(event)

        correo = body.get("correo")

    if not correo:
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "correo es obligatorio"})
        }

    # Validar permisos según reglas de negocio (Admin / Gerente / Cliente)
    usuario_autenticado = obtener_usuario_autenticado(event)
    tiene_acceso, error = validar_acceso_usuario(usuario_autenticado, correo)
    if not tiene_acceso:
        return {
            "statusCode": 403,
            "body": json.dumps({"message": error})
        }

    try:
        resp = usuarios_table.get_item(Key={"correo": correo})

        if "Item" not in resp:
            return {
                "statusCode": 404,
                "body": json.dumps({"message": "Usuario no encontrado"})
            }

        usuario = resp["Item"]

        # Remover contraseña de la respuesta
        if "contrasena" in usuario:
            del usuario["contrasena"]

        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "Usuario encontrado", "usuario": usuario}, default=str)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"message": f"Error al buscar usuario: {str(e)}"})
        }
