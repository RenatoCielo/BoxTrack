from django.apps import apps
from django.db import connection
from django.test import TestCase


DOMAIN_APPS = (
    'accounts', 'clubs', 'athletes', 'trainers', 'groups', 'trainings',
    'attendance', 'evaluations', 'weight_tracking', 'competitions',
    'alerts', 'notifications', 'store',
)

EXPECTED_TABLES = {
    'accounts.Role': 'roles',
    'accounts.User': 'usuarios',
    'clubs.Club': 'clubes',
    'athletes.Athlete': 'deportistas',
    'trainers.TrainerProfile': 'perfiles_entrenadores',
    'groups.Group': 'grupos',
    'trainings.Training': 'clases',
    'trainings.TrainingReservation': 'reservas_clases',
    'attendance.Attendance': 'asistencias',
    'evaluations.Evaluation': 'evaluaciones',
    'weight_tracking.WeightRecord': 'registros_peso',
    'competitions.Competition': 'competencias',
    'alerts.Alert': 'alertas',
    'notifications.Notification': 'notificaciones',
    'store.StoreSettings': 'configuracion_tienda',
    'store.Product': 'productos',
    'store.Order': 'pedidos',
    'store.OrderItem': 'detalle_pedidos',
}


class SpanishDatabaseSchemaTests(TestCase):
    def test_business_tables_and_columns_use_spanish_names(self):
        models = [
            model
            for app_label in DOMAIN_APPS
            for model in apps.get_app_config(app_label).get_models()
        ]
        self.assertEqual(
            {model._meta.label: model._meta.db_table for model in models},
            EXPECTED_TABLES,
        )

        with connection.cursor() as cursor:
            existing_tables = set(connection.introspection.table_names(cursor))
            for model in models:
                table_name = model._meta.db_table
                self.assertIn(table_name, existing_tables)
                actual_columns = {
                    column.name
                    for column in connection.introspection.get_table_description(cursor, table_name)
                }
                expected_columns = {field.column for field in model._meta.local_fields}
                self.assertTrue(
                    expected_columns.issubset(actual_columns),
                    f'{table_name} no contiene todas sus columnas: '
                    f'{expected_columns - actual_columns}',
                )
