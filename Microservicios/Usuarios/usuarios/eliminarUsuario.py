import json
import boto3
import os
from utils.authentication_utils import obtener_usuario_autenticado, verificar_rol, verificar_rol_solicitado
from utils.cors_utils import get_cors_headers

TABLE_USUARIOS_NAME = os.getenv("TABLE_USUARIOS", "ChinaWok-Usuarios")

dynamodb = boto3.resource("dynamodb")
usuarios_table = dynamodb.Table(TABLE_USUARIOS_NAME)


def lambda_handler(event, context):
    # Obtener usuario autenticado (centralizado)
    usuario_autenticado = obtener_usuario_autenticado(event)

    # Detectar ruta literal /usuario/me (ruta fija, sin pathParameters)
    path = (event.get("path") or "").lower()

    # Intentar leer pathParameters (para /usuario/{correo})
    path_params = event.get("pathParameters") or {}
    path_correo = path_params.get("correo")

    # Caso especial: DELETE /usuario/me (ruta fija)
    if path.endswith("/usuario/me"):
        correo_a_eliminar = usuario_autenticado["correo"]

    # Caso dinámico: DELETE /usuario/{correo}
    elif path_correo:
        if path_correo == "me":
            correo_a_eliminar = usuario_autenticado["correo"]
        else:
            correo_a_eliminar = path_correo

    # Fallback: correo en el body
    else:
        body = {}
        raw_body = event.get("body")

        if isinstance(raw_body, str) and raw_body:
            body = json.loads(raw_body)
        elif isinstance(raw_body, dict):
            body = raw_body

        correo_a_eliminar = body.get("correo")

    # Validación final
    if not correo_a_eliminar:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "message": "correo es obligatorio (path /usuario/{correo}, /usuario/me o body)"
            })
        }

    # Obtener información del usuario a eliminar
    resp = usuarios_table.get_item(Key={"correo": correo_a_eliminar})
    if "Item" not in resp:
        return {
            "statusCode": 404,
            "body": json.dumps({"message": "Usuario no encontrado"})
        }

    usuario_a_eliminar = resp["Item"]
    role_a_eliminar = usuario_a_eliminar.get("role", "Cliente")

    # Lógica de permisos
    es_admin = verificar_rol(usuario_autenticado, ["Admin"])
    es_gerente = verificar_rol(usuario_autenticado, ["Gerente"])
    es_mismo_usuario = usuario_autenticado["correo"] == correo_a_eliminar

    # Todos pueden eliminarse a sí mismos
    if es_mismo_usuario:
        usuarios_table.delete_item(Key={"correo": correo_a_eliminar})
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "Usuario eliminado correctamente"})
        }

    # Gerente puede eliminar solo Clientes
    if es_gerente:
        if role_a_eliminar == "Cliente":
            usuarios_table.delete_item(Key={"correo": correo_a_eliminar})
            return {
                "statusCode": 200,
                "headers": get_cors_headers(),
                "body": json.dumps({"message": "Usuario eliminado correctamente"})
            }
        else:
            return {
                "statusCode": 403,
                "body": json.dumps({"message": "Gerente solo puede eliminar Clientes"})
            }

    # Admin puede eliminar a todos
    if es_admin:
        usuarios_table.delete_item(Key={"correo": correo_a_eliminar})
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "Usuario eliminado correctamente"})
        }

    # Si no cumple ninguna condición
    return {
        "statusCode": 403,
        "body": json.dumps({"message": "No tienes permiso para eliminar este usuario"})
    }
