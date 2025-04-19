from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Establecer la configuración de Django por defecto para celery
# Asegúrate de que 'hospital_document_management.settings' sea el path correcto
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hospital_document_management.settings')

# El nombre de la aplicación Celery (puede ser el nombre de tu proyecto Django)
app = Celery('hospital_document_management')

# Usar la configuración de Django para Celery, usando un namespace 'CELERY'
# Esto significa que todas las claves de configuración de Celery deben empezar con CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Cargar tareas automáticamente de todas las apps registradas en INSTALLED_APPS
# Celery buscará un módulo 'tasks.py' en cada app.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}') 