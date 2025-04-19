from django.apps import AppConfig


class CorrespondenciaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'correspondencia'
    verbose_name = 'Gestión de Correspondencia' # Nombre legible para el admin

    def ready(self):
        # Importar y conectar las señales cuando la app esté lista
        import correspondencia.signals
