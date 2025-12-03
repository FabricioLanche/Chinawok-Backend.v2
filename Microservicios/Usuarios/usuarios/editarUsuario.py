import boto3
import os
import json
import re
from utils.authentication_utils import obtener_usuario_autenticado, verificar_rol
from utils.cors_utils import get_cors_headers

TABLE_USUARIOS_NAME = os.getenv("TABLE_USUARIOS", "ChinaWok-Usuarios")

dynamodb = boto3.resource("dynamodb")
usuarios_table = dynamodb.Table(TABLE_USUARIOS_NAME)


def _parse_body(event):
    body = event.get("body", {})
    if isinstance(body, str):
        body = json.loads(body) if body.strip() else {}
    elif not isinstance(body, dict):
        body = {}
    return body


def validar_informacion_bancaria(info_bancaria):
    """Valida el esquema de informacion_bancaria"""
    if not isinstance(info_bancaria, dict):
        return False, "informacion_bancaria debe ser un objeto"

    # Verificar campos requeridos
    campos_requeridos = ["numero_tarjeta", "cvv", "fecha_vencimiento", "direccion_delivery"]
    for campo in campos_requeridos:
        if campo not in info_bancaria:
            return False, f"Campo requerido faltante: {campo}"

    # Validar numero_tarjeta: 13-19 dígitos
    numero_tarjeta = info_bancaria.get("numero_tarjeta", "")
    if not re.match(r"^[0-9]{13,19}$", numero_tarjeta):
        return False, "numero_tarjeta debe tener entre 13 y 19 dígitos"

    # Validar CVV: 3-4 dígitos
    cvv = info_bancaria.get("cvv", "")
    if not re.match(r"^[0-9]{3,4}$", cvv):
        return False, "cvv debe tener 3 o 4 dígitos"

    # Validar fecha_vencimiento: MM/YY
    fecha_vencimiento = info_bancaria.get("fecha_vencimiento", "")
    if not re.match(r"^(0[1-9]|1[0-2])/[0-9]{2}$", fecha_vencimiento):
        return False, "fecha_vencimiento debe tener formato MM/YY"

    # Validar direccion_delivery
    direccion_delivery = info_bancaria.get("direccion_delivery", "")
    if not isinstance(direccion_delivery, str) or not direccion_delivery.strip():
        return False, "direccion_delivery debe ser una cadena no vacía"

    # No permitir campos adicionales
    campos_permitidos = set(campos_requeridos)
    campos_extra = set(info_bancaria.keys()) - campos_permitidos
    if campos_extra:
        return False, f"Campos no permitidos: {', '.join(campos_extra)}"

    return True, None


def lambda_handler(event, context):
    body = _parse_body(event)
    # Obtener usuario autenticado de forma centralizada
    usuario_autenticado = obtener_usuario_autenticado(event)

    # Determinar el correo objetivo: preferir path parameter /usuarios/{correo} o /usuarios/me
    path_params = event.get("pathParameters") or {}
    path_correo = path_params.get("correo")
    if path_correo:
        if path_correo == "me":
            correo = usuario_autenticado["correo"]
        else:
            correo = path_correo
    else:
        # Fallback antiguo: body.correo
        correo = body.get("correo")

    if not correo:
       return {"statusCode": 400, "body": json.dumps({"message": "correo es obligatorio (path /usuarios/{correo} o body)"})}

    # 🔒 Verificar permisos: Admin puede modificar a cualquiera, otros solo a sí mismos
    es_admin = verificar_rol(usuario_autenticado, ["Admin"])
    es_mismo_usuario = usuario_autenticado["correo"] == correo
    if not (es_admin or es_mismo_usuario):
        return {
            "statusCode": 403,
            "body": json.dumps({"message": "Solo puedes modificar tu propio perfil"})
        }

    resp = usuarios_table.get_item(Key={"correo": correo})
    if "Item" not in resp:
        return {
            "statusCode": 404,
            "body": json.dumps({"message": "Usuario no encontrado"})
        }

    update_expr = "SET "
    expr_attr_values = {}
    expr_attr_names = {}
    updates = []

    # Campos permitidos para actualizar
    if "nombre" in body:
        updates.append("#nombre = :nombre")
        expr_attr_names["#nombre"] = "nombre"
        expr_attr_values[":nombre"] = body["nombre"]

    if "contrasena" in body:
        if len(body["contrasena"]) < 6:
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "contrasena debe tener al menos 6 caracteres"})
            }
        updates.append("contrasena = :contrasena")
        expr_attr_values[":contrasena"] = body["contrasena"]

    # Validar role solo si se incluye
    if "role" in body:
        # 🔒 Solo Admin puede cambiar roles
        if not es_admin:
            return {
                "statusCode": 403,
                "body": json.dumps({"message": "Solo Admin puede cambiar roles"})
            }
        
        if body["role"] not in ["Cliente", "Gerente", "Admin"]:
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "role debe ser Cliente, Gerente o Admin"})
            }
        updates.append("#role = :role")
        expr_attr_names["#role"] = "role"
        expr_attr_values[":role"] = body["role"]

    # Validar informacion_bancaria si se incluye
    if "informacion_bancaria" in body:
        es_valido, error = validar_informacion_bancaria(body["informacion_bancaria"])
        if not es_valido:
            return {
                "statusCode": 400,
                "body": json.dumps({"message": f"informacion_bancaria inválida: {error}"})
            }
        updates.append("informacion_bancaria = :informacion_bancaria")
        expr_attr_values[":informacion_bancaria"] = body["informacion_bancaria"]

    if not updates:
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "No hay campos para actualizar"})
        }

    update_expr += ", ".join(updates)

    kwargs = {
        "Key": {"correo": correo},
        "UpdateExpression": update_expr,
        "ExpressionAttributeValues": expr_attr_values,
        "ReturnValues": "ALL_NEW"
    }
    
    if expr_attr_names:
        kwargs["ExpressionAttributeNames"] = expr_attr_names

    updated_item = usuarios_table.update_item(**kwargs)

    return {
        "statusCode": 200,
        "headers": get_cors_headers(),
        "body": json.dumps({"message": "Usuario actualizado correctamente", "usuario": updated_item["Attributes"]}, default=str)
    }
