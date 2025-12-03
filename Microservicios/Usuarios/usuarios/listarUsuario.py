import json
import boto3
import os
from utils.authentication_utils import obtener_usuario_autenticado, verificar_rol
from utils.cors_utils import get_cors_headers

TABLE_USUARIOS_NAME = os.getenv("TABLE_USUARIOS", "ChinaWok-Usuarios")

dynamodb = boto3.resource("dynamodb")
usuarios_table = dynamodb.Table(TABLE_USUARIOS_NAME)


def lambda_handler(event, context):
    # Obtener usuario autenticado (centralizado)
    usuario_autenticado = obtener_usuario_autenticado(event)
    # 🔒 Solo Admin puede listar todos los usuarios
    if not verificar_rol(usuario_autenticado, ["Admin"]):
        return {
            "statusCode": 403,
            "body": json.dumps({"message": "Acceso denegado. Solo Admin puede listar usuarios."})
        }
    
    try:
        response = usuarios_table.scan()
        usuarios = response.get("Items", [])
        
        # Remover contraseñas de la respuesta
        for usuario in usuarios:
            if "contrasena" in usuario:
                del usuario["contrasena"]
        
        return {
            "statusCode": 200,
            "headers": get_cors_headers(),
            "body": json.dumps({"message": "Usuarios obtenidos correctamente", "usuarios": usuarios}, default=str)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"message": f"Error al listar usuarios: {str(e)}"})
        }
