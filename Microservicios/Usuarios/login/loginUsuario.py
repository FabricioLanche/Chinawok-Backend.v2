import json
import boto3
import os
from utils.jwt_utils import generar_token
from utils.cors_utils import get_cors_headers

dynamodb = boto3.resource("dynamodb")
table_name = os.getenv("TABLE_USUARIOS", "ChinaWok-Usuarios")
usuarios_table = dynamodb.Table(table_name)


def lambda_handler(event, context):
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
        else:
            body = {}
    elif isinstance(event, dict):
        body = event
    elif isinstance(event, str):
        body = json.loads(event)

    correo = body.get("correo")
    contrasena = body.get("contrasena")

    if not correo or not contrasena:
        return {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "correo y contrasena son obligatorios"})
        }

    resp = usuarios_table.get_item(Key={"correo": correo})
    if "Item" not in resp:
        return {
            "statusCode": 401,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "Credenciales inválidas"})
        }

    usuario = resp["Item"]

    if usuario.get("contrasena") != contrasena:
        return {
            "statusCode": 401,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "Credenciales inválidas"})
        }

    token = generar_token(
        correo=usuario["correo"],
        role=usuario.get("role", "Cliente"),
        nombre=usuario.get("nombre", "")
    )
    
    # Construir objeto de usuario para la respuesta
    usuario_response = {
        "correo": usuario["correo"],
        "nombre": usuario["nombre"],
        "role": usuario["role"]
    }
    
    # Agregar local_id solo si existe (gerentes)
    if "local_id" in usuario:
        usuario_response["local_id"] = usuario["local_id"]

    return {
        "statusCode": 200,
        "headers": get_cors_headers(),
        "body": json.dumps({
            "message": "Login exitoso",
            "token": token,
            "usuario": usuario_response
        })
    }
