import os
from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError


class TransbankUnavailable(Exception):
    pass


def transbank_configured():
    return bool(
        os.getenv('TRANSBANK_ENVIRONMENT', 'TEST').upper() == 'TEST'
        and os.getenv('TRANSBANK_COMMERCE_CODE')
        and os.getenv('TRANSBANK_API_KEY')
    )


def webpay_transaction():
    if not transbank_configured():
        raise TransbankUnavailable('Transbank Webpay Plus no está configurado para pruebas.')
    try:
        from transbank.common.integration_type import IntegrationType
        from transbank.common.options import WebpayOptions
        from transbank.webpay.webpay_plus.transaction import Transaction
    except ImportError as error:
        raise TransbankUnavailable('Instala la dependencia oficial transbank-sdk para habilitar Webpay.') from error
    options = WebpayOptions(
        os.environ['TRANSBANK_COMMERCE_CODE'], os.environ['TRANSBANK_API_KEY'], IntegrationType.TEST,
    )
    return Transaction(options)


def clp_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError({'payment_method': 'El monto para Transbank no es válido.'}) from error
    if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
        raise ValidationError({'payment_method': 'Transbank Webpay Plus solo acepta montos CLP enteros.'})
    return int(amount)


def response_value(response, key):
    if isinstance(response, dict):
        return response.get(key)
    getter = getattr(response, 'get', None)
    if callable(getter):
        value = getter(key)
        if value is not None:
            return value
    return getattr(response, key, None)
