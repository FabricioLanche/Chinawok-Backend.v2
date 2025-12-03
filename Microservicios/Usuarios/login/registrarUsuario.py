import json
import boto3
import os
from datetime import datetime, timezone
from utils.jwt_utils import generar_token
from utils.cors_utils import get_cors_headers

TABLE_USUARIOS_NAME = os.getenv("TABLE_USUARIOS", "ChinaWok-Usuarios")

dynamodb = boto3.resource("dynamodb")
usuarios_table = dynamodb.Table(TABLE_USUARIOS_NAME)

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

    nombre = body.get("nombre")
    correo = body.get("correo")
    contrasena = body.get("contrasena")

    if not nombre or not correo or not contrasena:
        return {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "nombre, correo y contrasena son obligatorios"})
        }

    # Validar longitud mínima de contraseña
    if len(contrasena) < 6:
        return {
            "statusCode": 400,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "contrasena debe tener al menos 6 caracteres"})
        }

    resp = usuarios_table.get_item(Key={"correo": correo})
    if "Item" in resp:
        return {
            "statusCode": 409,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "Usuario ya existe"})
        }

    # El rol siempre se inicializa como "Cliente"
    item = {
        "nombre": nombre,
        "correo": correo,
        "contrasena": contrasena,
        "role": "Cliente",
        "historial_pedidos": [],
        "informacion_bancaria": None
    }

    usuarios_table.put_item(Item=item)

    # Generar token automáticamente al crear usuario
    token = generar_token(
        correo=correo,
        role="Cliente",
        nombre=nombre
    )

    return {
        "statusCode": 201,
        "headers": get_cors_headers(),
        "body": json.dumps({
            "message": "Usuario creado correctamente",
            "token": token,
            "usuario": {
                "correo": correo,
                "nombre": nombre,
                "role": "Cliente"
            }
        })
    }
