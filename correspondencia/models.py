from django.db import models
from django.conf import settings
from django.utils import timezone
from documentos.models import OficinaProductora, SerieDocumental, SubserieDocumental
import os # Necesario para os.path
from datetime import timedelta # Necesario para cálculos de fecha
from django.urls import reverse

# Choices para campos
TIPO_RADICADO_CHOICES = [
    ('ENTRANTE', 'Entrante'),
    # ('CIRCULAR', 'Circular Interna'), # Descomentar si se añade en el futuro
]

MEDIO_RECEPCION_CHOICES = [
    ('FISICO', 'Físico'),
    ('ELECTRONICO', 'Electrónico'),
]

# Estados para Correspondencia (Entrada)
ESTADOS_CORRESPONDENCIA = (
    ('RADICADA', 'Radicada'),
    ('ASIGNADA_USUARIO', 'Asignada a Usuario'),
    ('LEIDA', 'Leída por Oficina'),
    ('RESPONDIDA', 'Respondida'),
    # Añadir otros estados si existen en el modelo Correspondencia
)

TIEMPO_RESPUESTA_CHOICES = [
    ('NORMAL', 'Normal (15 días hábiles)'),
    ('URGENTE', 'Urgente (5 días hábiles)'),
    ('MUY_URGENTE', 'Muy Urgente (3 días hábiles)'),
]

# === NUEVO MODELO ENTIDAD EXTERNA ===
class EntidadExterna(models.Model):
    """Representa una entidad externa (empresa, institución, etc.)."""
    nombre = models.CharField(max_length=255, unique=True, help_text="Nombre completo de la entidad externa")
    nit = models.CharField(max_length=20, blank=True, null=True, help_text="NIT o identificador fiscal (opcional)")
    direccion = models.CharField(max_length=255, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    # Otros campos que consideres necesarios (ciudad, etc.)

    class Meta:
        verbose_name = "Entidad Externa"
        verbose_name_plural = "Entidades Externas"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @classmethod
    def get_entidad_por_defecto(cls):
        """Obtiene o crea la entidad por defecto 'Sin entidad'."""
        entidad, created = cls.objects.get_or_create(
            nombre="Sin entidad",
            defaults={
                'nit': None,
                'direccion': None,
                'telefono': None
            }
        )
        return entidad

# === FIN MODELO ENTIDAD EXTERNA ===

# === MODELO CONTACTO MODIFICADO ===
class Contacto(models.Model):
    """Representa un contacto externo (persona) asociado a una EntidadExterna."""
    entidad_externa = models.ForeignKey(
        EntidadExterna,
        on_delete=models.PROTECT, # Proteger para no borrar entidades con contactos asociados
        related_name='contactos',
        verbose_name="Entidad Externa",
        default=1  # Asumimos que la entidad "Sin entidad" tendrá ID 1
    )
    nombres = models.CharField(max_length=150, default="Sin nombre")
    apellidos = models.CharField(max_length=150, blank=True, null=True)
    # entidad = models.CharField(max_length=255, help_text="Nombre de la empresa, institución u organización") # CAMPO ANTIGUO ELIMINADO
    cargo = models.CharField(max_length=150, blank=True, null=True, help_text="Cargo del contacto dentro de la entidad (opcional)")
    correo_electronico = models.EmailField(max_length=254, blank=True, null=True)
    telefono_contacto = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono del Contacto")

    class Meta:
        verbose_name = "Contacto Externo"
        verbose_name_plural = "Contactos Externos"
        ordering = ['entidad_externa__nombre', 'apellidos', 'nombres'] # Ordenar por entidad, luego apellido
        constraints = [
            # Se podría ajustar el constraint si es necesario, quizás permitir mismo nombre en diferentes entidades?
            models.UniqueConstraint(fields=['entidad_externa', 'nombres', 'apellidos', 'correo_electronico'], name='contacto_unico_por_entidad')
        ]

    @property
    def nombre_completo(self):
        if self.apellidos:
            return f"{self.nombres} {self.apellidos}"
        return self.nombres

    def __str__(self):
        # Mostrar Nombre (Entidad) - Correo si existe
        identificador = f" ({self.correo_electronico})" if self.correo_electronico else ""
        return f"{self.nombre_completo} ({self.entidad_externa.nombre}){identificador}"
# === FIN MODELO CONTACTO ===

class Correspondencia(models.Model):
    """Modelo principal para registrar la correspondencia entrante."""
    
    # --- Campos de Radicación --- 
    numero_radicado = models.CharField(max_length=50, unique=True, editable=False)
    tipo_radicado = models.CharField(max_length=20, choices=TIPO_RADICADO_CHOICES, default='ENTRANTE')
    fecha_radicacion = models.DateTimeField(default=timezone.now, editable=False)
    usuario_radicador = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='correspondencia_radicada'
    )
    
    # --- Información del Documento (REEMPLAZAR remitente_externo) --- 
    # remitente_externo = models.CharField(max_length=255, help_text="Nombre de la persona o entidad externa que envía") # CAMPO ANTIGUO
    remitente = models.ForeignKey(
        Contacto, # Ahora se refiere al Contacto (persona)
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='correspondencias_enviadas',
        help_text="Seleccione el contacto (persona) que envía"
    )
    # Podríamos añadir opcionalmente una FK directa a EntidadExterna si queremos registrarla 
    # explícitamente en la correspondencia, aunque ya está implícita a través del Contacto.
    # entidad_remitente = models.ForeignKey(EntidadExterna, on_delete=models.SET_NULL, null=True, blank=True)
    asunto = models.TextField()
    serie = models.ForeignKey(SerieDocumental, on_delete=models.SET_NULL, null=True, blank=True)
    subserie = models.ForeignKey(SubserieDocumental, on_delete=models.SET_NULL, null=True, blank=True)
    medio_recepcion = models.CharField(
        max_length=50,
        choices=MEDIO_RECEPCION_CHOICES, 
        default='FISICO'
    )
    # Podríamos añadir un campo FileField aquí o un modelo relacionado para adjuntos más adelante
    # archivo_adjunto = models.FileField(upload_to='correspondencia_adjuntos/', null=True, blank=True)
    
    # --- Respuesta y Estado --- 
    requiere_respuesta = models.BooleanField(default=False)
    tiempo_respuesta = models.CharField(max_length=20, choices=TIEMPO_RESPUESTA_CHOICES, null=True, blank=True)
    estado = models.CharField(
        max_length=50,
        choices=ESTADOS_CORRESPONDENCIA, # Usar la constante definida
        default='RADICADA'
    )
    leido_por_oficina = models.BooleanField(default=False, help_text="Indica si alguien de la oficina destino ya lo leyó")
    resumen_ia = models.TextField(blank=True, null=True, help_text="Resumen del contenido generado por IA")
    
    # --- Distribución Inicial (Ventanilla) --- 
    oficina_destino = models.ForeignKey(
        OficinaProductora, 
        on_delete=models.PROTECT, # Evitar borrar oficinas con correspondencia pendiente?
        related_name='correspondencia_recibida'
    )
    usuario_destino_inicial = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='correspondencia_asignada_directa'
    )

    class Meta:
        verbose_name = "Correspondencia" # Nombre singular
        verbose_name_plural = "Correspondencias" # Nombre plural
        ordering = ['-fecha_radicacion'] # Ordenar por fecha descendente por defecto

    def __str__(self):
        return f"{self.numero_radicado} - {self.asunto[:50]}..."

    # --- Propiedades Calculadas para Plazo de Respuesta --- 
    @property
    def fecha_limite_respuesta(self):
        """Calcula la fecha límite de respuesta basada en fecha_radicacion y tiempo_respuesta."""
        if not self.requiere_respuesta or not self.tiempo_respuesta or not self.fecha_radicacion:
            return None

        dias_plazo = {
            'NORMAL': 15,
            'URGENTE': 5,
            'MUY_URGENTE': 3,
        }.get(self.tiempo_respuesta, 0)

        if dias_plazo == 0:
            return None
        
        # --- Cálculo Simple (Días Calendario) --- 
        # return self.fecha_radicacion + timedelta(days=dias_plazo)
        
        # --- Cálculo Mejorado (Excluyendo Fines de Semana - Aproximación a días hábiles) ---
        fecha_limite = self.fecha_radicacion
        dias_sumados = 0
        while dias_sumados < dias_plazo:
            fecha_limite += timedelta(days=1)
            # Contar solo si NO es sábado (5) o domingo (6)
            if fecha_limite.weekday() < 5: 
                dias_sumados += 1
        return fecha_limite

    @property
    def dias_restantes(self):
        """Calcula los días restantes hasta la fecha límite. Negativo si ya pasó."""
        fecha_limite = self.fecha_limite_respuesta
        if not fecha_limite:
            return None
        
        hoy = timezone.now().date()
        # Necesitamos comparar solo las fechas
        fecha_limite_date = fecha_limite.date()
        
        # Calcular diferencia en días
        delta = fecha_limite_date - hoy
        
        # --- Lógica simple de días restantes --- 
        # return delta.days

        # --- Lógica Mejorada (contando días hábiles restantes) --- 
        # Si ya pasó la fecha, los días restantes son negativos (diferencia calendario)
        if delta.days < 0:
             return delta.days
             
        # Si no ha pasado, contar días hábiles entre hoy y la fecha límite (incluyendo hoy si es hábil?)
        dias_habiles_restantes = 0
        fecha_actual = hoy
        while fecha_actual <= fecha_limite_date:
             # Contar si no es sábado o domingo
             if fecha_actual.weekday() < 5:
                 dias_habiles_restantes += 1
             fecha_actual += timedelta(days=1)
             
        # Restamos 1 porque el bucle incluye el día de hoy, 
        # queremos los días que *faltan* sin contar hoy.
        # Si hoy es un día hábil, el resultado debe ser >= 0
        # Si hoy es fin de semana, el primer día hábil contará como 1 día restante.
        return max(0, dias_habiles_restantes -1) if hoy.weekday() < 5 else dias_habiles_restantes
        
    @property
    def estado_plazo(self):
        """Devuelve una cadena indicando el estado del plazo para usar en clases CSS, etc."""
        dias = self.dias_restantes
        if dias is None:
            return 'na' # No aplica o no requiere respuesta
        
        if dias < 0:
            return 'vencido' # Rojo Fuerte
        elif dias <= 1: # Último día o mañana
            return 'critico' # Rojo
        elif dias <= 3: # Urgente
            return 'urgente' # Naranja
        elif dias <= 7: # Próximo
            return 'proximo' # Amarillo
        else:
            return 'ok' # Verde o normal
            
    # --- Fin Propiedades Calculadas ---

    def save(self, *args, **kwargs):
        if not self.pk: # Si es un objeto nuevo (no tiene Primary Key aún)
            self.numero_radicado = self._generar_numero_radicado()
        
        # Validación: tiempo_respuesta solo si requiere_respuesta es True
        if not self.requiere_respuesta:
            self.tiempo_respuesta = None
        elif not self.tiempo_respuesta: # Si requiere respuesta pero no se especificó tiempo, poner Normal?
             self.tiempo_respuesta = 'NORMAL' # O lanzar ValidationError
             # raise ValidationError("Si requiere respuesta, debe especificar el tiempo de respuesta.")

        super().save(*args, **kwargs) # Llamar al método save original

    def _generar_numero_radicado(self):
        """Genera un número de radicado único basado en tipo y año."""
        from django.utils import timezone
        now = timezone.now()
        current_year = now.year
        tipo_prefijo = self.tipo_radicado # Ej: ENTRANTE
        
        # Buscar el último radicado de este tipo y año
        last_radicado = Correspondencia.objects.filter(
            tipo_radicado=self.tipo_radicado,
            fecha_radicacion__year=current_year
        ).order_by('fecha_radicacion').last() # Podría ser más eficiente ordenar por ID o radicado si el formato es consistente
        
        if last_radicado and last_radicado.numero_radicado:
            try:
                # Intentar extraer el último consecutivo
                parts = last_radicado.numero_radicado.split('-')
                last_consecutive = int(parts[-1])
                next_consecutive = last_consecutive + 1
            except (IndexError, ValueError):
                # Si el formato anterior es inesperado, empezar de 1
                next_consecutive = 1
        else:
            next_consecutive = 1
            
        # Formatear el nuevo número
        # Asegura 5 dígitos con ceros a la izquierda (ej: 00001, 00123, 12345)
        return f"{tipo_prefijo}-{current_year}-{next_consecutive:05d}"

class HistorialCorrespondencia(models.Model):
    """Registra los eventos y cambios de estado de una correspondencia."""
    correspondencia = models.ForeignKey(
        Correspondencia, 
        on_delete=models.CASCADE, 
        related_name='historial'
    )
    fecha_hora = models.DateTimeField(default=timezone.now)
    # Usamos los mismos choices de estado para registrar el evento
    evento = models.CharField(max_length=30, choices=ESTADOS_CORRESPONDENCIA)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, # Puede haber eventos sin usuario (ej: lectura automática IA?)
        related_name='acciones_correspondencia'
    )
    # Campo opcional para añadir detalles o notas sobre el evento
    descripcion = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Historial de Correspondencia"
        verbose_name_plural = "Historiales de Correspondencia"
        ordering = ['-fecha_hora'] # Mostrar el evento más reciente primero

    def __str__(self):
        user_display = f" por {self.usuario.username}" if self.usuario else ""
        return f"{self.correspondencia.numero_radicado} - {self.get_evento_display()}{user_display} el {self.fecha_hora.strftime('%Y-%m-%d %H:%M')}"

# --- ¿Modelo para Distribución a Oficina? --- 
# Si la distribución inicial solo va a UNA oficina, el campo `oficina_destino` 
# en `Correspondencia` podría ser suficiente. Si una correspondencia pudiera 
# distribuirse a MÚLTIPLES oficinas INICIALMENTE (poco común para entrante),
# necesitaríamos un modelo ManyToMany aquí.

# --- ¿Modelo para Redistribución Interna a Usuarios? ---
# Podríamos necesitar un modelo ManyToMany para rastrear a qué usuarios específicos
# dentro de la `oficina_destino` se les ha redistribuido.
# Ejemplo:
# class DistribucionInternaUsuario(models.Model):
#     correspondencia = models.ForeignKey(Correspondencia, on_delete=models.CASCADE)
#     usuario_asignado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     fecha_asignacion = models.DateTimeField(default=timezone.now)
#     asignado_por = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='asignaciones_realizadas', on_delete=models.SET_NULL, null=True)
#     leido = models.BooleanField(default=False)

# Por ahora, nos enfocaremos en añadir HistorialCorrespondencia.

# === NUEVO MODELO ADJUNTO CORREO ===
def ruta_adjunto_correo(instance, filename):
    """Genera la ruta donde se guardarán los adjuntos de correos."""
    # archivo va a /media/correspondencia/email_adjuntos/<correspondencia_id>/<filename>
    # Asegurarse que instance.correspondencia exista y tenga id
    correspondencia_id = instance.correspondencia.id if instance.correspondencia and instance.correspondencia.id else 'sin_asignar'
    return os.path.join('correspondencia', 'email_adjuntos', str(correspondencia_id), filename)

class AdjuntoCorreo(models.Model):
    """Representa un archivo adjunto asociado a una correspondencia electrónica."""
    correspondencia = models.ForeignKey(
        Correspondencia,
        on_delete=models.CASCADE, # Si se borra la correspondencia, se borran sus adjuntos
        related_name='adjuntos_correo'
    )
    archivo = models.FileField(
        upload_to=ruta_adjunto_correo,
        max_length=255 # Aumentar si nombres de archivo pueden ser muy largos
    )
    nombre_original = models.CharField(max_length=255, blank=True, help_text="Nombre original del archivo en el correo")
    tipo_mime = models.CharField(max_length=100, blank=True, help_text="Tipo MIME detectado del archivo")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Adjunto de Correo"
        verbose_name_plural = "Adjuntos de Correo"
        ordering = ['-fecha_carga']

    def __str__(self):
        # Devolver solo el nombre del archivo
        return os.path.basename(self.archivo.name) if self.archivo else "(Sin archivo)"

    def save(self, *args, **kwargs):
        # Guardar nombre original si no se proporcionó
        if not self.nombre_original and self.archivo:
            # Asegurarse que el archivo tenga nombre antes de accederlo
            try:
                 self.nombre_original = os.path.basename(self.archivo.name)
            except Exception:
                 self.nombre_original = "archivo_desconocido"
        super().save(*args, **kwargs)

# === FIN MODELO ADJUNTO CORREO ===

# === NUEVO MODELO CORREO ENTRANTE (FASE 2) ===
class CorreoEntrante(models.Model):
    """Almacena temporalmente correos leídos de IMAP antes de procesarlos."""
    message_id = models.CharField(max_length=255, unique=True, help_text="Message-ID único del correo")
    remitente = models.EmailField()
    asunto = models.CharField(max_length=500, blank=True) # Aumentar longitud para asuntos largos
    cuerpo_texto = models.TextField(blank=True, help_text="Cuerpo del mensaje en texto plano")
    cuerpo_html = models.TextField(blank=True, help_text="Cuerpo del mensaje en HTML (si existe)")
    fecha_recepcion_original = models.DateTimeField(null=True, blank=True, help_text="Fecha del encabezado 'Date' del correo")
    fecha_lectura_imap = models.DateTimeField(default=timezone.now)
    procesado = models.BooleanField(default=False, db_index=True, help_text="Indica si ya se intentó la clasificación IA")
    radicado_asociado = models.ForeignKey(
        'Correspondencia', # Usar string para evitar importación circular si Correspondencia está después
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='correo_origen',
        help_text="Correspondencia creada a partir de este correo (si aplica)"
    )
    # Campo para marcar si necesita revisión humana
    requiere_revision_manual = models.BooleanField(default=False, help_text="Marcar si la radicación automática falló y necesita intervención.")
    
    # --- Campos para clasificación IA (sin tipo_clasificado) ---
    oficina_clasificada = models.ForeignKey(
        OficinaProductora,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='correos_clasificados_oficina', # Cambiado related_name para evitar conflicto
        help_text="Oficina destino predicha por IA"
    )
    serie_clasificada = models.ForeignKey(
        SerieDocumental,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='correos_clasificados_serie',
        help_text="Serie documental predicha por IA"
    )
    subserie_clasificada = models.ForeignKey(
        SubserieDocumental,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='correos_clasificados_subserie',
        help_text="Subserie documental predicha por IA (relacionada a la serie)"
    )
    fecha_clasificacion = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha y hora en que se realizó la clasificación IA"
    )
    # --- Fin campos IA ---

    class Meta:
        verbose_name = "Correo Entrante IMAP"
        verbose_name_plural = "Correos Entrantes IMAP"
        ordering = ['-fecha_lectura_imap']

    def __str__(self):
        return f"De: {self.remitente} - Asunto: {self.asunto[:60]}... ({self.fecha_lectura_imap.strftime('%Y-%m-%d %H:%M')})"

# === FIN MODELO CORREO ENTRANTE ===

# --- Función para ruta de adjuntos de CorreoEntrante ---
def ruta_adjunto_correo_entrante(instance, filename):
    """Genera la ruta donde se guardarán los adjuntos de correos entrantes."""
    # archivo va a /media/correos_entrantes/adjuntos/<correo_entrante_id>/<filename>
    correo_id = instance.correo_entrante.id if instance.correo_entrante and instance.correo_entrante.id else 'sin_asignar'
    # Limpiar nombre de archivo para evitar problemas de ruta
    clean_filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c.isspace() or c in ['.','-','_']]).rstrip()
    return os.path.join('correos_entrantes', 'adjuntos', str(correo_id), clean_filename)

# --- NUEVO MODELO ADJUNTO CORREO ENTRANTE ---
class AdjuntoCorreoEntrante(models.Model):
    """Representa un archivo adjunto asociado a un CorreoEntrante."""
    correo_entrante = models.ForeignKey(
        CorreoEntrante,
        on_delete=models.CASCADE, # Si se borra el CorreoEntrante, se borran sus adjuntos
        related_name='adjuntos' # Nombre de relación simple
    )
    archivo = models.FileField(
        upload_to=ruta_adjunto_correo_entrante,
        max_length=255
    )
    nombre_original = models.CharField(max_length=255, blank=True, help_text="Nombre original del archivo en el correo")
    tipo_mime = models.CharField(max_length=100, blank=True, help_text="Tipo MIME detectado del archivo")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Adjunto de Correo Entrante"
        verbose_name_plural = "Adjuntos de Correo Entrante"
        ordering = ['-fecha_carga']

    def __str__(self):
        return os.path.basename(self.archivo.name) if self.archivo else "(Sin archivo)"

    def save(self, *args, **kwargs):
        # Guardar nombre original si no se proporcionó y existe archivo
        if not self.nombre_original and self.archivo and hasattr(self.archivo, 'name'):
             try:
                 self.nombre_original = os.path.basename(self.archivo.name)
             except Exception:
                 self.nombre_original = "archivo_adjunto" # Fallback
        super().save(*args, **kwargs)
# === FIN MODELO ADJUNTO CORREO ENTRANTE ===

class DistribucionInternaUsuario(models.Model):
    """Modelo para rastrear la redistribución de correspondencia a usuarios específicos dentro de una oficina."""
    correspondencia = models.ForeignKey(Correspondencia, on_delete=models.CASCADE, related_name='distribuciones_internas')
    usuario_asignado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='correspondencia_asignada')
    fecha_asignacion = models.DateTimeField(default=timezone.now)
    asignado_por = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='asignaciones_realizadas', on_delete=models.SET_NULL, null=True)
    leido = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Distribución Interna"
        verbose_name_plural = "Distribuciones Internas"
        ordering = ['-fecha_asignacion']
        unique_together = ['correspondencia', 'usuario_asignado']

    def __str__(self):
        return f"{self.correspondencia.numero_radicado} -> {self.usuario_asignado.username}"

# =============================================
# === MODELOS PARA CORRESPONDENCIA DE SALIDA ===
# =============================================

# Estados para CorrespondenciaSalida
ESTADOS_SALIDA = (
    ('BORRADOR', 'Borrador'),
    ('PENDIENTE_APROBACION', 'Pendiente Aprobación'),
    ('APROBADA', 'Aprobada'),
    ('RECHAZADA', 'Rechazada'),
    ('ENVIADA', 'Enviada'),
    ('ERROR_ENVIO', 'Error de Envío'),
)

class CorrespondenciaSalida(models.Model):
    """Representa una respuesta o comunicación de salida."""
    respuesta_a = models.ForeignKey(
        Correspondencia, 
        on_delete=models.PROTECT, # Proteger la entrada original
        related_name='respuestas_salientes',
        help_text="Correspondencia entrante a la que responde este documento."
    )
    numero_radicado_salida = models.CharField(max_length=50, unique=True, editable=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    usuario_redactor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='correspondencia_redactada'
    )
    fecha_ultima_modificacion = models.DateTimeField(auto_now=True)

    # Destinatario (fijo, basado en el remitente original)
    destinatario_contacto = models.ForeignKey(
        Contacto, 
        on_delete=models.PROTECT, # Proteger al contacto 
        related_name='correspondencia_recibida_saliente',
        editable=False, # No editable en el formulario
        help_text="Contacto externo al que se dirige la respuesta (automático)."
    )
    destinatario_email = models.EmailField(
        editable=False, # No editable, se llena al aprobar
        help_text="Email del destinatario al momento de la aprobación (automático)."
    )

    asunto = models.CharField(max_length=255)
    cuerpo = models.TextField()

    # Flujo de Aprobación y Envío
    estado = models.CharField(
        max_length=50, 
        choices=ESTADOS_SALIDA, # Usar la constante definida
        default='BORRADOR'
    )
    usuario_aprobador = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='correspondencia_aprobada'
    )
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True, null=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    id_mensaje_enviado = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Correspondencia de Salida"
        verbose_name_plural = "Correspondencias de Salida"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Respuesta {self.numero_radicado_salida} a {self.respuesta_a.numero_radicado}"

    def save(self, *args, **kwargs):
        if not self.pk: # Si es nuevo
            # Asegurar que el destinatario_contacto se establezca al crear
            if not self.destinatario_contacto and self.respuesta_a and self.respuesta_a.remitente:
                 self.destinatario_contacto = self.respuesta_a.remitente
            # Generar radicado solo al crear
            self.numero_radicado_salida = self._generar_numero_radicado_salida()
        
        # Rellenar email justo antes de intentar enviar (o al aprobar)
        if self.estado == 'APROBADA' and not self.destinatario_email and self.destinatario_contacto:
             self.destinatario_email = self.destinatario_contacto.correo_electronico
             
        super().save(*args, **kwargs)

    def _generar_numero_radicado_salida(self):
        """Genera un número de radicado único para la correspondencia de salida."""
        now = timezone.now()
        current_year = now.year
        prefijo = "SALIENTE" 
        
        last_radicado = CorrespondenciaSalida.objects.filter(
            fecha_creacion__year=current_year
        ).order_by('fecha_creacion').last()
        
        next_consecutive = 1
        if last_radicado and last_radicado.numero_radicado_salida:
            try:
                parts = last_radicado.numero_radicado_salida.split('-')
                last_consecutive = int(parts[-1])
                next_consecutive = last_consecutive + 1
            except (IndexError, ValueError):
                pass # Mantener next_consecutive = 1
                
        return f"{prefijo}-{current_year}-{next_consecutive:05d}"

# --- Modelo para Adjuntos de Salida ---
def ruta_adjunto_salida(instance, filename):
    """Genera la ruta para guardar adjuntos de salida."""
    salida_id = instance.correspondencia_salida.id if instance.correspondencia_salida and instance.correspondencia_salida.id else 'sin_asignar'
    # Limpiar nombre de archivo 
    clean_filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c.isspace() or c in ['.','-','_']]).rstrip()
    return os.path.join('correspondencia', 'salida_adjuntos', str(salida_id), clean_filename)

class AdjuntoSalida(models.Model):
    """Representa un archivo adjunto asociado a una correspondencia de salida."""
    correspondencia_salida = models.ForeignKey(
        CorrespondenciaSalida,
        on_delete=models.CASCADE,
        related_name='adjuntos'
    )
    archivo = models.FileField(upload_to=ruta_adjunto_salida, max_length=255)
    nombre_original = models.CharField(max_length=255, blank=True)
    tipo_mime = models.CharField(max_length=100, blank=True)
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Adjunto de Salida"
        verbose_name_plural = "Adjuntos de Salida"
        ordering = ['-fecha_carga']

    def __str__(self):
        return self.nombre_original or os.path.basename(self.archivo.name)

    def save(self, *args, **kwargs):
        if not self.nombre_original and self.archivo and hasattr(self.archivo, 'name'):
             try:
                 self.nombre_original = os.path.basename(self.archivo.name)
             except Exception:
                 self.nombre_original = "adjunto_salida"
        super().save(*args, **kwargs)

# --- Modelo de Historial para Salida ---
TIPO_EVENTO_SALIDA_CHOICES = [
    ('CREACION', 'Creación Borrador'),
    ('MODIFICACION', 'Modificación Borrador'),
    ('ENVIO_APROBACION', 'Enviado a Aprobación'),
    ('APROBACION', 'Aprobado por Ventanilla'),
    ('RECHAZO', 'Rechazado por Ventanilla'),
    ('INTENTO_ENVIO', 'Intento de Envío Email'),
    ('ENVIO_EXITOSO', 'Email Enviado Exitosamente'),
    ('ENVIO_FALLIDO', 'Error al Enviar Email'),
]

class HistorialSalida(models.Model):
    """Registra los eventos clave en el ciclo de vida de una correspondencia de salida."""
    correspondencia_salida = models.ForeignKey(
        CorrespondenciaSalida, 
        on_delete=models.CASCADE, 
        related_name='historial'
    )
    fecha_hora = models.DateTimeField(default=timezone.now)
    tipo_evento = models.CharField(max_length=30, choices=TIPO_EVENTO_SALIDA_CHOICES)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True
    )
    descripcion = models.TextField(blank=True, null=True, help_text="Detalles adicionales, motivo rechazo, error envío...")
    
    class Meta:
        verbose_name = "Historial de Correspondencia Salida"
        verbose_name_plural = "Historiales de Correspondencia Salida"
        ordering = ['-fecha_hora']

    def __str__(self):
        user_display = f" por {self.usuario.username}" if self.usuario else ""
        return f"{self.correspondencia_salida.numero_radicado_salida} - {self.get_tipo_evento_display()}{user_display}"
