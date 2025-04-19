from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import CorreoEntrante, Correspondencia, Contacto, HistorialCorrespondencia
import logging

logger = logging.getLogger(__name__)

# Constantes de confianza (ajustar según sea necesario)
CONFIANZA_MINIMA_CLASIFICACION = 0.8 # Ejemplo: Umbral de confianza para clasif. IA

@receiver(post_save, sender=CorreoEntrante)
def intentar_radicacion_automatica(sender, instance, created, **kwargs):
    """Señal que intenta radicar automáticamente un correo cuando se marca como procesado."""
    # Solo actuar si el correo está procesado, no está radicado, no requiere revisión, y no se está creando (para evitar loops si se guarda de nuevo)
    if instance.procesado and not instance.radicado_asociado and not instance.requiere_revision_manual and not created:
        logger.info(f"[AutoRad] Iniciando intento de radicación para CorreoEntrante ID: {instance.pk}")
        
        radicado_exitoso = False
        mensaje_error = ""

        try:
            with transaction.atomic(): # Asegurar atomicidad
                # --- 1. Manejo de Contacto --- 
                contacto = buscar_o_crear_contacto_auto(instance.remitente)
                if not contacto:
                    mensaje_error = "No se pudo determinar/crear el contacto."
                    raise ValueError(mensaje_error)
                logger.info(f"[AutoRad] Contacto determinado/creado: {contacto.id}")

                # --- 2. Validación de Clasificación --- 
                # Aquí iría la lógica para verificar la confianza de la IA si estuviera disponible
                # if instance.confianza_clasificacion < CONFIANZA_MINIMA_CLASIFICACION:
                #     mensaje_error = "Confianza de clasificación IA demasiado baja."
                #     raise ValueError(mensaje_error)
                
                # Validar que los campos clasificados no sean nulos (asumiendo que son obligatorios para radicar)
                if not instance.oficina_clasificada or not instance.serie_clasificada:
                    mensaje_error = "Falta Oficina o Serie clasificada por IA."
                    raise ValueError(mensaje_error)
                logger.info("[AutoRad] Clasificación IA validada.")

                # --- 3. Determinación de Respuesta y Tiempo (Lógica Placeholder) --- 
                # !! Lógica muy básica, necesita IA real o reglas más complejas !!
                requiere_respuesta = False
                tiempo_respuesta = None
                if "solicitud" in instance.asunto.lower() or "pregunta" in instance.asunto.lower() or "requiero" in instance.cuerpo_texto.lower():
                    requiere_respuesta = True
                    tiempo_respuesta = 'NORMAL' # Asumir normal por defecto
                logger.info(f"[AutoRad] Requiere respuesta: {requiere_respuesta}, Tiempo: {tiempo_respuesta}")

                # --- 4. Creación de Correspondencia --- 
                correspondencia = Correspondencia.objects.create(
                    # tipo_radicado se asume ENTRANTE por defecto
                    remitente=contacto,
                    asunto=instance.asunto,
                    serie=instance.serie_clasificada,
                    subserie=instance.subserie_clasificada, # Puede ser None si la IA no lo asignó
                    medio_recepcion='ELECTRONICO', # Asumir electrónico si viene de CorreoEntrante
                    requiere_respuesta=requiere_respuesta,
                    tiempo_respuesta=tiempo_respuesta,
                    oficina_destino=instance.oficina_clasificada,
                    estado='RADICADA' # Estado inicial después de radicar
                    # usuario_radicador podría ser None o un usuario sistema si se crea
                )
                logger.info(f"[AutoRad] Correspondencia {correspondencia.numero_radicado} creada.")

                # --- 5. Asociar Correo y Crear Historial --- 
                instance.radicado_asociado = correspondencia
                instance.save(update_fields=['radicado_asociado']) # Guardar solo el campo cambiado
                logger.info(f"[AutoRad] CorreoEntrante {instance.pk} asociado a Correspondencia {correspondencia.numero_radicado}.")

                HistorialCorrespondencia.objects.create(
                    correspondencia=correspondencia,
                    evento='RADICADA',
                    descripcion="Radicada automáticamente desde correo electrónico."
                    # usuario podría ser None o un usuario sistema
                )
                logger.info("[AutoRad] Historial 'RADICADA' creado.")

                radicado_exitoso = True

        except Exception as e:
            # Si algo falla, marcar para revisión manual
            logger.error(f"[AutoRad] Error al radicar CorreoEntrante {instance.pk}: {e}")
            instance.requiere_revision_manual = True
            instance.save(update_fields=['requiere_revision_manual'])
            # Podríamos enviar una notificación al administrador aquí
            
        if radicado_exitoso:
             logger.info(f"[AutoRad] Radicación automática exitosa para CorreoEntrante {instance.pk}.")
        else:
             logger.warning(f"[AutoRad] Radicación automática fallida para CorreoEntrante {instance.pk}. Marcado para revisión manual. Razón: {mensaje_error}")

def buscar_o_crear_contacto_auto(email_remitente):
    """Lógica (simplificada) para encontrar o crear un contacto basado en email."""
    try:
        # Intenta encontrar por email exacto (ignorar mayúsculas/minúsculas)
        contacto = Contacto.objects.get(correo_electronico__iexact=email_remitente)
        return contacto
    except Contacto.DoesNotExist:
        # Si no existe, crear uno muy básico
        # !! Esta lógica debería mejorarse extrayendo más info del correo si es posible !!
        try:
            nombre_entidad = f"Entidad de {email_remitente}" # Nombre muy genérico
            contacto = Contacto.objects.create(
                correo_electronico=email_remitente,
                entidad=nombre_entidad
                # nombres y apellidos quedarían nulos por ahora
            )
            logger.info(f"[AutoRad] Contacto creado automáticamente para {email_remitente}")
            return contacto
        except Exception as e:
            logger.error(f"[AutoRad] Error al crear contacto para {email_remitente}: {e}")
            return None # Falló la creación
    except Contacto.MultipleObjectsReturned:
        # Si hay varios contactos con el mismo email (debería evitarse con constraint)
        logger.warning(f"[AutoRad] Múltiples contactos encontrados para {email_remitente}. Se requiere intervención manual.")
        return None # Requiere intervención manual 