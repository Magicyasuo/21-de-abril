from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

@shared_task(name='correspondencia.tasks.procesar_emails_periodico')
def procesar_emails_periodico():
    """Tarea periódica para ejecutar el comando manage.py procesar_emails."""
    try:
        logger.info("Iniciando tarea periódica: procesar_emails")
        # Ejecutar el comando de Django
        call_command('procesar_emails')
        logger.info("Tarea periódica procesar_emails finalizada exitosamente.")
    except Exception as e:
        logger.error(f"Error ejecutando la tarea periódica procesar_emails: {e}", exc_info=True)
        # Puedes decidir si reintentar la tarea aquí o manejar el error de otra forma
        # Por ejemplo, raise self.retry(exc=e, countdown=60) # Reintentar en 60 segundos
        pass # Por ahora, solo logueamos el error 