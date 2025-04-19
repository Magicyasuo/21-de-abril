import os
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.conf import settings
import os
import logging

logger = logging.getLogger(__name__)

def validate_file_size(value):
    max_size = 2 * 1024 * 1024  # 2 MB - corregido de comentario original
    if value.size > max_size:
        raise ValidationError(f"El archivo no puede superar los 2 MB. Tamaño actual: {value.size / (1024 * 1024):.2f} MB")

def normalize_filename(filename):
    """Normaliza el nombre del archivo eliminando caracteres especiales y espacios"""
    name, extension = os.path.splitext(filename)
    return f"{slugify(name)}{extension.lower()}"

def documento_upload_path(instance, filename):
    """
    Construye la ruta de almacenamiento basada en la oficina, serie, subserie y registro.
    """
    filename = normalize_filename(filename)
    
    try:
        if instance.registro.creado_por.perfil.oficina:
            oficina = slugify(instance.registro.creado_por.perfil.oficina.nombre)
        else:
            oficina = "sin_oficina"
    except AttributeError:
        oficina = "sin_oficina"
    
    try:
        # Usamos el nombre de la serie/subserie
        serie = slugify(instance.registro.codigo_serie.nombre)
        subserie = slugify(instance.registro.codigo_subserie.nombre) if instance.registro.codigo_subserie else "00"
        registro_id = str(instance.registro.id)
    except AttributeError:
        serie = "serie_default"
        subserie = "subserie_default"
        registro_id = "0"
    
    ruta = os.path.join("documentos", oficina, f"serie_{serie}", f"subserie_{subserie}", f"registro_{registro_id}")
    
    ruta_completa = os.path.join(settings.MEDIA_ROOT, ruta)
    os.makedirs(ruta_completa, exist_ok=True)
    return os.path.join(ruta, filename)


def validate_file_extension(value):
    ext = os.path.splitext(value.name)[1].lower()  # p. ej. ".pdf"
    valid_extensions = ['.pdf', '.xls', '.xlsx', '.doc', '.docx']
    if ext not in valid_extensions:
        raise ValidationError("Solo se permiten archivos PDF, Excel o Word.")


class SerieDocumental(models.Model):
    codigo = models.CharField(max_length=50)
    nombre = models.CharField(max_length=255)
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

class SubserieDocumental(models.Model):
    codigo = models.CharField(max_length=50)
    nombre = models.CharField(max_length=255)
    serie = models.ForeignKey(SerieDocumental, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre} (Serie: {self.serie.nombre})"

class EntidadProductora(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    
    def __str__(self):
        return self.nombre

class UnidadAdministrativa(models.Model):
    nombre = models.CharField(max_length=255)
    entidad_productora = models.ForeignKey(EntidadProductora, on_delete=models.CASCADE, related_name='unidades')
    
    def __str__(self):
        return f"{self.nombre} ({self.entidad_productora.nombre})"

class OficinaProductora(models.Model):
    nombre = models.CharField(max_length=255)
    unidad_administrativa = models.ForeignKey(UnidadAdministrativa, on_delete=models.CASCADE, related_name='oficinas')
    
    def __str__(self):
        return f"{self.nombre} ({self.unidad_administrativa.nombre})"

class Objeto(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    
    def __str__(self):
        return self.nombre

class FUID(models.Model):
    entidad_productora = models.ForeignKey(EntidadProductora, on_delete=models.SET_NULL, null=True)
    unidad_administrativa = models.ForeignKey(UnidadAdministrativa, on_delete=models.SET_NULL, null=True)
    oficina_productora = models.ForeignKey(OficinaProductora, on_delete=models.SET_NULL, null=True)
    objeto = models.ForeignKey(Objeto, on_delete=models.SET_NULL, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='fuids')
    registros = models.ManyToManyField('RegistroDeArchivo', related_name='fuids', blank=True)
    
    elaborado_por_nombre = models.CharField(max_length=255, null=True, blank=True)
    elaborado_por_cargo = models.CharField(max_length=255, null=True, blank=True)
    elaborado_por_lugar = models.CharField(max_length=255, null=True, blank=True)
    elaborado_por_fecha = models.DateField(null=True, blank=True)
    
    entregado_por_nombre = models.CharField(max_length=255, null=True, blank=True)
    entregado_por_cargo = models.CharField(max_length=255, null=True, blank=True)
    entregado_por_lugar = models.CharField(max_length=255, null=True, blank=True)
    entregado_por_fecha = models.DateField(null=True, blank=True)
    
    recibido_por_nombre = models.CharField(max_length=255, null=True, blank=True)
    recibido_por_cargo = models.CharField(max_length=255, null=True, blank=True)
    recibido_por_lugar = models.CharField(max_length=255, null=True, blank=True)
    recibido_por_fecha = models.DateField(null=True, blank=True)

    class Meta:
        permissions = [
            ("view_own_fuid", "Puede ver sus propios FUIDs"),
            ("edit_own_fuid", "Puede editar sus propios FUIDs"),
            ("delete_own_fuid", "Puede eliminar sus propios FUIDs"),
        ]
    
    def __str__(self):
        return f"FUID #{self.id} - {self.entidad_productora.nombre if self.entidad_productora else 'Sin Entidad'}"




class RegistroDeArchivo(models.Model):  
    Estado_archivo = models.BooleanField(default=True)
    numero_orden = models.IntegerField(default=0)  # Identificador único
    codigo = models.CharField(max_length=50, blank=True, null=True)
    codigo_serie = models.ForeignKey(SerieDocumental, on_delete=models.CASCADE, related_name="registros")
    codigo_subserie = models.ForeignKey(SubserieDocumental, on_delete=models.CASCADE, blank=True, null=True, related_name="registros")
    unidad_documental = models.CharField(max_length=255)
    fecha_archivo = models.DateField(blank=True, null=True) #va al final
    fecha_inicial = models.DateField(blank=True, null=True)
    fecha_final = models.DateField(blank=True, null=True)
    soporte_fisico = models.BooleanField(default=False)
    soporte_electronico = models.BooleanField(default=False)

    # llave foreanea para el fuid
    # fuid = models.ForeignKey(FUID, on_delete=models.SET_NULL, null=True, blank=True, related_name='registros')

    # campos fisicos
    caja = models.IntegerField(blank=True, null=True)
    carpeta = models.IntegerField(blank=True, null=True)
    tomo_legajo_libro = models.CharField(max_length=50, blank=True, null=True)
    numero_folios = models.IntegerField(blank=True, null=True)
    tipo = models.CharField(max_length=100, blank=True, null=True)
    cantidad = models.IntegerField(blank=True, null=True)
    # campos electronicos
    ubicacion = models.CharField(max_length=255, null=True)
    cantidad_documentos_electronicos = models.IntegerField(null=True, blank=True)
    tamano_documentos_electronicos = models.CharField(max_length=50, null=True, blank=True)

    # agrego identificacion del documento para casos como la historia clinica
    identificador_documento  = models.IntegerField(null=True, blank=True)

    notas = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ("view_own_registro", "Puede ver sus propios registros"),
            ("edit_own_registro", "Puede editar sus propios registros"),
            ("delete_own_registro", "Puede eliminar sus propios registros"),
        ]


from django.core.exceptions import ValidationError

class Documento(models.Model):
    registro = models.ForeignKey('RegistroDeArchivo', on_delete=models.CASCADE, related_name='documentos')
    archivo = models.FileField(upload_to=documento_upload_path, validators=[validate_file_size],max_length=300)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.pk and self.registro.documentos.count() >= 3:
            raise ValidationError("Solo se permiten 3 archivos por registro.")
        
        # Antes de guardar, asegurarse de que el directorio existe
        if self.archivo:
            ruta_destino = os.path.dirname(os.path.join(settings.MEDIA_ROOT, self.archivo.field.upload_to(self, self.archivo.name)))
            try:
                os.makedirs(ruta_destino, exist_ok=True, mode=0o755)  # Crea el directorio con permisos adecuados
                logger.info(f"Directorio creado/verificado: {ruta_destino}")
            except PermissionError as e:
                logger.error(f"Error de permisos al crear directorio {ruta_destino}: {str(e)}")
                raise ValidationError(f"No se pueden crear los directorios necesarios debido a permisos insuficientes. Por favor contacte al administrador del sistema.")
            except Exception as e:
                logger.error(f"Error al crear directorio {ruta_destino}: {str(e)}")
                raise ValidationError(f"Error al crear directorio para almacenar el archivo: {str(e)}")
                
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Documento para registro {self.registro.numero_orden}"


    


class PermisoUsuarioSerie(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    serie = models.ForeignKey(SerieDocumental, on_delete=models.CASCADE)
    permiso_crear = models.BooleanField(default=False)
    permiso_editar = models.BooleanField(default=False)
    permiso_consultar = models.BooleanField(default=True)
    permiso_eliminar = models.BooleanField(default=False)

    def __str__(self):
        return f"Permisos de {self.usuario.username} sobre {self.serie.nombre}"


class FichaPaciente (models.Model):
    consecutivo = models.AutoField(primary_key=True)
    primer_nombre = models.CharField(max_length=50)
    segundo_nombre = models.CharField(max_length=50, blank=True, null=True)
    primer_apellido = models.CharField(max_length=50)
    segundo_apellido = models.CharField(max_length=50, blank=True, null=True)
    num_identificacion = models.IntegerField(unique=True)
    fecha_nacimiento = models.DateField()
    primer_nombre_padre = models.CharField(max_length=50, blank=True, null=True)
    segundo_nombre_padre = models.CharField(max_length=50, blank=True, null=True)
    primer_apellido_padre = models.CharField(max_length=50, blank=True, null=True)
    segundo_apellido_padre = models.CharField(max_length=50, blank=True, null=True)
    Numero_historia_clinica = models.IntegerField(unique=True)
    caja = models.CharField(max_length=20)
    carpeta = models.CharField(max_length=20)
    gabeta= models.IntegerField(null=True, blank=True)
    tipo_identificacion = models.CharField(max_length=20, default='Cedula de Ciudadania')
    sexo = models.CharField(max_length=10, default='Masculino')
    activo = models.BooleanField(default=True)

        

    

    def __str__(self):
        return f"Ficha del paciente  {self.primer_nombre} con identificacion {self.num_identificacion}"
    

# models.py

from django.db import models
from django.contrib.auth.models import User

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    oficina = models.ForeignKey(OficinaProductora, on_delete=models.CASCADE)
    cargo = models.CharField(max_length=150, blank=True, null=True, help_text="Cargo del usuario (opcional)")

    def __str__(self):
        return f"{self.user.username} - {self.oficina.nombre}"


