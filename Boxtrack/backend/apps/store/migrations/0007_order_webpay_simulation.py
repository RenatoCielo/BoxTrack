from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0006_rename_store_order_club_id_19278f_idx_pedidos_club_id_e6bb47_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='payment_method',
            field=models.CharField(
                choices=[
                    ('MERCADO_PAGO', 'Mercado Pago'),
                    ('WEBPAY', 'Webpay (simulación)'),
                    ('BANK_TRANSFER', 'Transferencia'),
                    ('RESERVE', 'Reserva para retiro'),
                ],
                db_column='metodo_pago',
                max_length=20,
            ),
        ),
    ]
