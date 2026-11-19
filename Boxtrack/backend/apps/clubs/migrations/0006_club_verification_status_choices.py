from django.db import migrations, models


def normalize_legacy_statuses(apps, schema_editor):
    Club = apps.get_model('clubs', 'Club')
    Club.objects.filter(
        verification_status__in=['IN_REVIEW', 'NEEDS_INFO']
    ).update(verification_status='PENDING')
    Club.objects.exclude(verification_status='APPROVED').update(is_public=False)


class Migration(migrations.Migration):

    dependencies = [
        ('clubs', '0005_club_is_public_plan'),
    ]

    operations = [
        migrations.RunPython(normalize_legacy_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='club',
            name='verification_status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pendiente'),
                    ('APPROVED', 'Aprobado'),
                    ('REJECTED', 'Rechazado'),
                ],
                db_column='estado_verificacion',
                default='PENDING',
                max_length=16,
            ),
        ),
    ]
