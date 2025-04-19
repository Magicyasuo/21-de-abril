from django.contrib import admin
from .models import (
    Correspondencia, 
    HistorialCorrespondencia, 
    Contacto, 
    CorreoEntrante, 
    AdjuntoCorreoEntrante, 
    AdjuntoCorreo,
    EntidadExterna
)

# Modelos básicos para visualización y gestión simple

@admin.register(Correspondencia)
class CorrespondenciaAdmin(admin.ModelAdmin):
    list_display = ('numero_radicado', 'fecha_radicacion', 'asunto', 'remitente', 'oficina_destino', 'serie', 'estado', 'leido_por_oficina')
    list_filter = ('estado', 'leido_por_oficina', 'oficina_destino', 'serie', 'fecha_radicacion')
    search_fields = ('numero_radicado', 'asunto', 'remitente__nombres', 'remitente__apellidos', 'remitente__entidad_externa__nombre')
    readonly_fields = ('numero_radicado', 'fecha_radicacion') # Campos generados automáticamente

@admin.register(CorreoEntrante)
class CorreoEntranteAdmin(admin.ModelAdmin):
    list_display = ('fecha_lectura_imap', 'remitente', 'asunto', 'procesado', 'oficina_clasificada', 'serie_clasificada', 'radicado_asociado')
    list_filter = ('procesado', 'fecha_lectura_imap', 'oficina_clasificada', 'serie_clasificada')
    search_fields = ('remitente', 'asunto', 'cuerpo')
    readonly_fields = ('fecha_lectura_imap',)

@admin.register(HistorialCorrespondencia)
class HistorialCorrespondenciaAdmin(admin.ModelAdmin):
    list_display = ('correspondencia', 'fecha_hora', 'evento', 'usuario', 'descripcion')
    list_filter = ('evento', 'fecha_hora', 'usuario')
    readonly_fields = ('fecha_hora',)

@admin.register(Contacto)
class ContactoAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'entidad_externa', 'cargo', 'correo_electronico', 'telefono_contacto')
    list_filter = ('entidad_externa',)
    search_fields = ('nombres', 'apellidos', 'correo_electronico', 'entidad_externa__nombre')
    list_select_related = ('entidad_externa',)

    fieldsets = (
        (None, {
            'fields': ('entidad_externa', 'nombres', 'apellidos', 'cargo')
        }),
        ('Información de Contacto', {
            'fields': ('correo_electronico', 'telefono_contacto')
        }),
    )

# Registrar modelos de adjuntos si se necesita gestión directa
admin.site.register(AdjuntoCorreoEntrante)
admin.site.register(AdjuntoCorreo)

@admin.register(EntidadExterna)
class EntidadExternaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nit', 'telefono')
    search_fields = ('nombre', 'nit')
