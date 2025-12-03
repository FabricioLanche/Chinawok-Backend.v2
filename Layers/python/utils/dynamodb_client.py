"""
Cliente de DynamoDB para operaciones comunes
"""
import boto3
from typing import List, Dict, Any
from decimal import Decimal

def get_dynamodb_resource():
    """
    Retorna un recurso de DynamoDB
    """
    return boto3.resource('dynamodb')


def get_table_data(table_name: str) -> List[Dict[str, Any]]:
    """
    Escanea una tabla de DynamoDB y retorna todos los items
    
    Args:
        table_name (str): Nombre de la tabla de DynamoDB
        
    Returns:
        List[Dict]: Lista de items de la tabla
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    
    items = []
    
    # Escanear todos los items (manejar paginación)
    response = table.scan()
    items.extend(response.get('Items', []))
    
    # Manejar paginación si hay más items
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    
    return items


def convert_decimal_to_float(obj):
    """
    Convierte recursivamente Decimal a float para serialización JSON
    """
    if isinstance(obj, list):
        return [convert_decimal_to_float(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj
