from decimal import Decimal
def custom_serializer(obj):
        if isinstance(obj,Decimal):
            return float(obj)
        return str(obj)