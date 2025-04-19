import imaplib
from functools import partial
from imap_tools import MailBox, AND, MailMessageFlags
import traceback
import os

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.core.files.base import ContentFile

from correspondencia.models import CorreoEntrante, AdjuntoCorreoEntrante

# --- Credenciales y config ---
IMAP_SERVER = 'imap.gmail.com'
IMAP_PORT = 993
EMAIL_ACCOUNT = 'hospitalsararecolombia@gmail.com'
EMAIL_PASSWORD = 'nrqxthjfdfejjipz'  # Contraseña de aplicación SIN espacios
# ----------------------------

class Command(BaseCommand):
    help = 'Lee correos no leídos, los guarda en CorreoEntrante y almacena sus adjuntos.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "--- ¡ADVERTENCIA! Usando credenciales directamente en el código. Mover a entorno para producción. ---"
        ))
        self.stdout.write(f"Iniciando procesamiento de emails desde {EMAIL_ACCOUNT}...")

        correos_guardados = 0
        adjuntos_guardados = 0
        errores = []
        mailbox = None

        try:
            self.stdout.write(f"Conectando a {IMAP_SERVER}:{IMAP_PORT} con SSL...")

            # Conexión IMAP segura compatible con todas las versiones
            mailbox = MailBox(IMAP_SERVER)
            mailbox._factory = partial(imaplib.IMAP4_SSL, IMAP_SERVER, IMAP_PORT)
            mailbox.login(EMAIL_ACCOUNT, EMAIL_PASSWORD, initial_folder='INBOX')
            self.stdout.write("Conectado. Buscando correos no leídos...")

            # Buscar correos NO VISTOS
            messages = mailbox.fetch(AND(seen=False), mark_seen=False, bulk=True) # No marcar como leídos aquí
            total_emails = 0
            emails_to_process = list(messages) # Convertir generador a lista para saber el total

            if not emails_to_process:
                self.stdout.write("No se encontraron correos nuevos no leídos.")
            else:
                 self.stdout.write(f"Se encontraron {len(emails_to_process)} correos nuevos no leídos.")

            for i, msg in enumerate(emails_to_process):
                total_emails += 1
                self.stdout.write(f"--- Procesando email {i+1}/{len(emails_to_process)}: UID={msg.uid}, Subject='{msg.subject}' ---")

                correo_entrante_obj = None # Para referencia en caso de error
                try:
                    message_id = msg.headers.get('message-id', [''])[0].strip("<>").strip()
                    if not message_id:
                        self.stdout.write(self.style.WARNING(f"  Email UID {msg.uid} sin Message-ID. Generando uno."))
                        # Generar uno un poco más robusto
                        message_id = f"<generated.{msg.uid}.{timezone.now().strftime('%Y%m%d%H%M%S%f')}@{EMAIL_ACCOUNT.split('@')[-1] if '@' in EMAIL_ACCOUNT else 'local.host'}>"

                    if CorreoEntrante.objects.filter(message_id=message_id).exists():
                        self.stdout.write(f"  Correo con Message-ID {message_id} ya existe. Marcando como leído y omitiendo.")
                        # Marcar como leído en el servidor si ya existe en BD
                        mailbox.flag(msg.uid, MailMessageFlags.SEEN, True)
                        continue

                    from_email = msg.from_ or "desconocido@dominio.com" # Evitar vacío
                    subject = msg.subject or "(Sin asunto)"
                    fecha_recepcion = msg.date or timezone.now() # Usar ahora si no hay fecha
                    if timezone.is_naive(fecha_recepcion):
                        # Intentar con zona horaria por defecto, o UTC como fallback
                        try:
                            fecha_recepcion = timezone.make_aware(fecha_recepcion, timezone.get_default_timezone())
                        except Exception:
                            fecha_recepcion = timezone.make_aware(fecha_recepcion, timezone.utc)


                    cuerpo_texto = msg.text or ""
                    cuerpo_html = msg.html or ""

                    with transaction.atomic():
                        # Crear el CorreoEntrante PRIMERO
                        correo_entrante_obj = CorreoEntrante.objects.create(
                            message_id=message_id,
                            remitente=from_email.lower(),
                            asunto=subject[:500], # Limitar longitud
                            cuerpo_texto=cuerpo_texto,
                            cuerpo_html=cuerpo_html,
                            fecha_recepcion_original=fecha_recepcion,
                        )
                        self.stdout.write(self.style.SUCCESS(f"  Creado registro CorreoEntrante ID: {correo_entrante_obj.id}"))
                        correos_guardados += 1

                        # Procesar y guardar adjuntos AHORA que tenemos el ID
                        num_adjuntos_correo = 0
                        if msg.attachments:
                             self.stdout.write(f"  Procesando {len(msg.attachments)} adjuntos...")
                             for att in msg.attachments:
                                 try:
                                     filename = att.filename or f"adjunto_{att.part.subtype}_{timezone.now().timestamp()}"
                                     content = att.payload # Contenido en bytes
                                     content_type = att.content_type or "application/octet-stream"

                                     adjunto = AdjuntoCorreoEntrante(
                                         correo_entrante=correo_entrante_obj,
                                         nombre_original=filename,
                                         tipo_mime=content_type
                                     )
                                     # Usar ContentFile para guardar desde bytes
                                     adjunto.archivo.save(filename, ContentFile(content), save=True)
                                     adjuntos_guardados += 1
                                     num_adjuntos_correo += 1
                                     self.stdout.write(f"    Guardado adjunto: {filename} (ID: {adjunto.id})")

                                 except Exception as e_att:
                                     detalle_error_att = traceback.format_exc()
                                     err_msg_att = f"Error guardando adjunto '{att.filename}' para correo UID {msg.uid}: {e_att}\\nDetalle: {detalle_error_att}"
                                     errores.append(err_msg_att)
                                     self.stdout.write(self.style.ERROR(f"    Error guardando adjunto '{att.filename}': {e_att}"))

                        # Marcar como leído en el servidor DESPUÉS de procesar (incluido adjuntos)
                        mailbox.flag(msg.uid, MailMessageFlags.SEEN, True)
                        self.stdout.write(self.style.SUCCESS(f"  Correo UID {msg.uid} procesado ({num_adjuntos_correo} adjuntos) y marcado como leído."))

                except Exception as e:
                    detalle_error = traceback.format_exc()
                    # Incluir message_id si se obtuvo
                    err_prefix = f"Error procesando email UID {msg.uid}"
                    if 'message_id' in locals() and message_id:
                        err_prefix += f" (Message-ID: {message_id})"
                    errores.append(f"{err_prefix}: {e}\\nDetalle: {detalle_error}")
                    self.stdout.write(self.style.ERROR(f"  {err_prefix}: {e}"))
                    # Si hubo error grave, NO marcar como leído para reintentar
                    # if mailbox and msg:
                    #     mailbox.flag(msg.uid, MailMessageFlags.SEEN, False) # Opcional: quitar bandera SEEN si falla

        except imaplib.IMAP4.error as e_imap:
             detalle_error = traceback.format_exc()
             errores.append(f"Error de conexión/autenticación IMAP: {e_imap}\\nDetalle: {detalle_error}")
             self.stdout.write(self.style.ERROR(f"Error IMAP: {e_imap}"))
             if "authentication failed" in str(e_imap).lower():
                 self.stdout.write(self.style.ERROR("--> Verifica las credenciales (email/contraseña de aplicación) y la configuración IMAP de la cuenta."))
             elif "please log in" in str(e_imap).lower():
                  self.stdout.write(self.style.ERROR("--> Error de login. Verifica credenciales."))
             else:
                 self.stdout.write(self.style.ERROR("--> Revisa la conexión a internet y la configuración del servidor IMAP."))

        except Exception as e_general:
            detalle_error = traceback.format_exc()
            errores.append(f"Error general en el script: {e_general}\\nDetalle: {detalle_error}")
            self.stdout.write(self.style.ERROR(f"Error general inesperado: {e_general}"))

        finally:
            if mailbox:
                try:
                    self.stdout.write("Cerrando conexión IMAP...")
                    mailbox.logout()
                    self.stdout.write("Conexión cerrada.")
                except Exception as e_logout:
                    # No añadir a errores principales, solo log
                    self.stdout.write(self.style.WARNING(f"Error menor al cerrar la conexión: {e_logout}"))

        self.stdout.write(self.style.SUCCESS("\n--- Proceso de lectura y guardado de correos completado ---"))
        self.stdout.write(f"Correos nuevos guardados en la BD: {correos_guardados}")
        self.stdout.write(f"Adjuntos guardados: {adjuntos_guardados}")
        if errores:
            self.stdout.write(self.style.ERROR(f"\nSe encontraron {len(errores)} ERRORES durante el proceso:"))
            for i, err in enumerate(errores):
                # Mostrar solo la primera línea del error para resumen
                self.stdout.write(self.style.ERROR(f"  Error {i+1}: {err.splitlines()[0]}"))
                # Opcional: Loggear el error completo a un archivo
                # logger.error(err)
        else:
            self.stdout.write(self.style.SUCCESS("No se reportaron errores."))
