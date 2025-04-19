from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from .views import (
    BandejaClasificadosView, BandejaRevisionManualView, DetalleCorreoClasificadoView, 
    radicar_correspondencia, lista_pendientes_distribuir, distribuir_correspondencia,
    listar_contactos, crear_contacto, home_view, ver_perfil, bandeja_entrada, 
    detalle_correspondencia, #marcar_como_leido, 
    redistribuir_interna, compartir_correspondencia,
    bandeja_personal, bandeja_oficina,
    bandeja_correos_pendientes_view, api_subseries, detalle_correo_entrante_view,
    listar_entidades, crear_entidad, 
    procesar_emails_manual,
    crear_o_editar_respuesta, bandeja_respuestas_pendientes, revisar_respuesta,
    HistorialCorrespondenciaView # <-- Añadir la nueva vista
)

app_name = 'correspondencia'  # Definir el espacio de nombres de la aplicación

urlpatterns = [
    path('', views.home_view, name='home'),
    path('welcome/', views.home_view, name='welcome'), 
    path('radicar/', views.radicar_correspondencia, name='radicar_manual'),
    path('radicar/desde-correo/<int:correo_id>/', views.radicar_correspondencia, name='radicar_desde_correo'),
    # path('bandeja/', views.bandeja_entrada, name='bandeja_entrada'), # <-- ELIMINADA/COMENTADA: Reemplazada por bandeja_personal
    path('correspondencia/<int:pk>/', views.detalle_correspondencia, name='detalle_correspondencia'),
    # path('correspondencia/<int:pk>/marcar_leido/', views.marcar_como_leido, name='marcar_leido'), # <-- COMENTADA: Funcionalidad ahora en detalle_correspondencia
    # Añadir URL para redistribución si se implementa
    path('perfil/', views.ver_perfil, name='ver_perfil'),

    # URL para la nueva bandeja de correos clasificados
    path('correos/clasificados/', views.BandejaClasificadosView.as_view(), name='bandeja_clasificados'),

    # Nueva URL para correos que requieren revisión manual
    path('correos/revision-manual/', views.BandejaRevisionManualView.as_view(), name='bandeja_revision_manual'),

    # Descomentar URL para la vista de detalle del correo clasificado
    path('correos/clasificados/<int:pk>/detalle/', views.DetalleCorreoClasificadoView.as_view(), name='detalle_correo_clasificado'),

    # --- Autenticación ---
    path('login/', LoginView.as_view(template_name='correspondencia/login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='correspondencia:login'), name='logout'), # Redirigir a login al salir

    # Nueva URL para la lista de pendientes
    path('pendientes-distribuir/', views.lista_pendientes_distribuir, name='pendientes_distribuir'),
    # Nueva URL para la acción de distribuir
    path('<int:pk>/distribuir/', views.distribuir_correspondencia, name='distribuir_correspondencia'),
    # Aquí añadiremos más URLs de correspondencia más adelante
    # path('bandeja/oficina/', views.bandeja_oficina, name='bandeja_oficina'),

    # Rutas de Contactos
    path('contactos/', views.listar_contactos, name='listar_contactos'),
    path('contactos/crear/', views.crear_contacto, name='crear_contacto'),
    # Aquí podríamos añadir URLs para editar y eliminar contactos más adelante

    # --- URLs Entidades Externas (NUEVO) ---
    path('entidades/', views.listar_entidades, name='listar_entidades'),
    path('entidades/crear/', views.crear_entidad, name='crear_entidad'),
    # Añadir URLs para editar/eliminar entidades si es necesario

    path('compartir/<int:pk>/', views.compartir_correspondencia, name='compartir_correspondencia'),
    # path('marcar-leido/<int:pk>/', views.marcar_como_leido, name='marcar_leido'), # <-- COMENTADA TAMBIÉN AQUÍ

    # --- URLs USUARIO REGULAR ---
    path('bandeja/', views.bandeja_personal, name='bandeja_personal'), 
    path('bandeja-oficina/', views.bandeja_oficina, name='bandeja_oficina'),
    # --- FIN URLs USUARIO REGULAR ---

    # --- URLs VENTANILLA (NUEVO) ---
    path('ventanilla/correos-pendientes/', views.bandeja_correos_pendientes_view, name='bandeja_correos_pendientes'),
    path('ventanilla/correo/<int:correo_id>/detalle/', views.detalle_correo_entrante_view, name='detalle_correo_entrante'),
    path('ventanilla/procesar-emails-manual/', views.procesar_emails_manual, name='procesar_emails_manual'),
    path('ventanilla/ajax/subseries/', views.api_subseries, name='ajax_subseries'),

    # path('ventanilla/correo/<int:correo_id>/radicar/', views.detalle_radicar_correo_view, name='detalle_radicar_correo'), # <-- ELIMINADA
    # --- FIN URLs VENTANILLA ---
    
    # === URLs PARA RESPUESTA DE CORRESPONDENCIA ===
    # Usuario Regular
    path('correspondencia/<int:correspondencia_entrada_id>/responder/', views.crear_o_editar_respuesta, name='crear_respuesta'),
    # Ventanilla
    path('ventanilla/respuestas-pendientes/', views.bandeja_respuestas_pendientes, name='bandeja_respuestas_pendientes'),
    path('ventanilla/respuesta/<int:respuesta_id>/revisar/', views.revisar_respuesta, name='revisar_respuesta'),
    # === FIN URLs RESPUESTA ===

    # --- Nueva URL para el Historial --- 
    path('historial/', HistorialCorrespondenciaView.as_view(), name='historial_correspondencia'),
] 