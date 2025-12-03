import json
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    """Encoder JSON personalizado para manejar objetos Decimal de DynamoDB"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            # Convertir Decimal a float si tiene decimales, sino a int
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def json_dumps(obj):
    """Helper para serializar JSON con soporte para Decimal"""
    return json.dumps(obj, cls=DecimalEncoder)
