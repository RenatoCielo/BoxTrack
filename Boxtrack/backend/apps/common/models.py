from django.db import models
from django.db.models.base import ModelBase


SPANISH_COLUMN_NAMES = {
    'password': 'contrasena_hash',
    'last_login': 'ultimo_inicio_sesion',
    'is_superuser': 'es_superusuario',
    'username': 'nombre_usuario',
    'first_name': 'nombre',
    'last_name': 'apellido',
    'email': 'correo',
    'is_staff': 'es_personal',
    'is_active': 'esta_activo',
    'date_joined': 'fecha_registro',
    'role': 'id_rol',
    'club': 'id_club',
    'phone': 'telefono',
    'nickname': 'apodo',
    'use_nickname': 'usar_apodo',
    'share_phone': 'compartir_telefono',
    'must_change_password': 'debe_cambiar_contrasena',
    'created_at': 'fecha_creacion',
    'updated_at': 'fecha_actualizacion',
    'name': 'nombre',
    'description': 'descripcion',
    'legal_rut': 'rut_legal',
    'legal_representative_name': 'nombre_representante_legal',
    'legal_representative_rut': 'rut_representante_legal',
    'verification_status': 'estado_verificacion',
    'verification_document': 'documento_verificacion',
    'verification_note': 'observacion_verificacion',
    'verification_submitted_at': 'fecha_envio_verificacion',
    'verified_at': 'fecha_verificacion',
    'verified_by': 'id_verificado_por',
    'address': 'direccion',
    'website': 'sitio_web',
    'disciplines': 'disciplinas',
    'logo': 'logotipo',
    'user': 'id_usuario',
    'first_name': 'nombre',
    'last_name': 'apellido',
    'photo': 'foto',
    'birth_date': 'fecha_nacimiento',
    'emergency_contact': 'contacto_emergencia',
    'admission_date': 'fecha_ingreso',
    'status': 'estado',
    'is_competitor': 'es_competidor',
    'assigned_trainer': 'id_entrenador_asignado',
    'group': 'id_grupo',
    'category': 'categoria',
    'registered_weight': 'peso_registrado',
    'guard': 'guardia',
    'experience': 'experiencia',
    'observations': 'observaciones',
    'specialty': 'especialidad',
    'experience_years': 'anos_experiencia',
    'professional_title': 'titulo_profesional',
    'bio': 'biografia',
    'schedule': 'horario',
    'title': 'titulo',
    'activity_type': 'tipo_actividad',
    'trainer': 'id_entrenador',
    'scheduled_date': 'fecha_programada',
    'start_time': 'hora_inicio',
    'duration_minutes': 'duracion_minutos',
    'capacity': 'capacidad',
    'objectives': 'objetivos',
    'training': 'id_clase',
    'athlete': 'id_deportista',
    'reserved_at': 'fecha_reserva',
    'registered_at': 'fecha_registro',
    'evaluator': 'id_evaluador',
    'evaluation_date': 'fecha_evaluacion',
    'technical': 'tecnica',
    'defense': 'defensa',
    'speed': 'velocidad',
    'endurance': 'resistencia',
    'power': 'potencia',
    'coordination': 'coordinacion',
    'mobility': 'movilidad',
    'general_condition': 'condicion_general',
    'strengths': 'fortalezas',
    'improvement_areas': 'areas_mejora',
    'next_goals': 'proximos_objetivos',
    'weight': 'peso',
    'recorded_date': 'fecha_registro',
    'opponent_name': 'nombre_oponente',
    'fight_date': 'fecha_pelea',
    'event': 'evento',
    'competition_date': 'fecha_competencia',
    'location': 'ubicacion',
    'result': 'resultado',
    'fight_type': 'tipo_pelea',
    'message': 'mensaje',
    'level': 'nivel',
    'source': 'origen',
    'is_resolved': 'esta_resuelta',
    'resolved_at': 'fecha_resolucion',
    'notification_type': 'tipo_notificacion',
    'is_read': 'esta_leida',
    'bank_transfer_instructions': 'instrucciones_transferencia',
    'sku': 'codigo_producto',
    'price': 'precio',
    'stock': 'stock',
    'image_url': 'url_imagen',
    'payment_method': 'metodo_pago',
    'payment_reference': 'referencia_pago',
    'checkout_url': 'url_pago',
    'payment_proof': 'comprobante_pago',
    'proof_status': 'estado_comprobante',
    'proof_review_note': 'nota_revision_comprobante',
    'proof_reviewed_by': 'id_revisado_por',
    'proof_reviewed_at': 'fecha_revision_comprobante',
    'expires_at': 'fecha_vencimiento',
    'shipping_address': 'direccion_entrega',
    'notes': 'notas',
    'total': 'total',
    'stock_released': 'stock_liberado',
    'order': 'id_pedido',
    'product': 'id_producto',
    'product_name': 'nombre_producto',
    'unit_price': 'precio_unitario',
    'quantity': 'cantidad',
    'subtotal': 'subtotal',
}


class SpanishSchemaModelBase(ModelBase):
    def __new__(metaclass, name, bases, attrs, **kwargs):
        model = super().__new__(metaclass, name, bases, attrs, **kwargs)
        if not model._meta.abstract:
            for field in model._meta.local_fields:
                if field.name == 'id':
                    continue
                try:
                    column_name = SPANISH_COLUMN_NAMES[field.name]
                except KeyError as error:
                    raise TypeError(
                        f'Falta el nombre de columna en español para '
                        f'{model._meta.label}.{field.name}.'
                    ) from error
                field.db_column = column_name
                field.column = column_name
        return model


class SpanishSchemaModel(models.Model, metaclass=SpanishSchemaModelBase):
    class Meta:
        abstract = True
