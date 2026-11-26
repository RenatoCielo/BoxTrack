from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0007_order_webpay_simulation'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='webpay_session_id',
            field=models.CharField(blank=True, db_column='id_sesion_webpay', max_length=61),
        ),
        migrations.AlterField(
            model_name='order',
            name='payment_method',
            field=models.CharField(
                choices=[
                    ('MERCADO_PAGO', 'Mercado Pago'),
                    ('WEBPAY', 'Webpay'),
                    ('BANK_TRANSFER', 'Transferencia'),
                    ('RESERVE', 'Reserva para retiro'),
                ],
                db_column='metodo_pago',
                max_length=20,
            ),
        ),
    ]
