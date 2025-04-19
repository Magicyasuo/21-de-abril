from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.contrib import messages
from .forms import CorrespondenciaForm, ContactoForm, CompartirCorrespondenciaForm, ManualRadicacionCorreoForm, EntidadExternaForm, RespuestaCorrespondenciaForm, AprobarRechazarRespuestaForm, HistorialFilterForm
from .models import Correspondencia, HistorialCorrespondencia, Contacto, CorreoEntrante, OficinaProductora, SerieDocumental, SubserieDocumental, AdjuntoCorreoEntrante, AdjuntoCorreo, DistribucionInternaUsuario, EntidadExterna, CorrespondenciaSalida, AdjuntoSalida, HistorialSalida
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, View
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from documentos.models import PerfilUsuario # Necesario para obtener perfil
from django.contrib.auth.models import User
from .models import DistribucionInternaUsuario
from django.db.models import Q, Count, Case, When, BooleanField # Para consultas OR y anotaciones
from django.core.management import call_command
from django.core.files.base import ContentFile
import traceback
from django.db.utils import IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_GET
# justo debajo de los imports de modelos
# views.py (encabezado)
from documentos.models import SubserieDocumental as SubserieDoc
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.mail import EmailMessage # <--- Añadir esta importación
from django.urls import reverse_lazy
from django.db.models.functions import Coalesce
from django.db.models import F # <-- Importar F
from django.db.models import Q # Importar Q para búsquedas complejas
from django.db import models # <-- IMPORTAR BASE MODELS


# Create your views here.

# --- Vista para la Bandeja de Correos Clasificados ---
class EsVentanillaMixin(UserPassesTestMixin):
    """Mixin para verificar si el usuario pertenece al grupo 'Ventanilla'."""
    def test_func(self):
        # Asume que tienes un grupo llamado 'Ventanilla'. Ajusta si es necesario.
        return self.request.user.groups.filter(name='Ventanilla').exists()

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permiso para acceder a esta sección.")
        # Redirigir a una página segura, por ejemplo, la home o welcome
        return redirect('correspondencia:welcome') # Ajusta el nombre de la URL si es diferente

class BandejaClasificadosView(LoginRequiredMixin, EsVentanillaMixin, ListView):
    model = CorreoEntrante
    template_name = 'correspondencia/bandeja_clasificados.html'
    context_object_name = 'correos_clasificados'
    # paginate_by = 15 # Quitar paginación del servidor

    def get_queryset(self):
        """Filtra correos procesados, no radicados y que NO requieren revisión manual."""
        queryset = CorreoEntrante.objects.filter(
            procesado=True,
            radicado_asociado__isnull=True,
            requiere_revision_manual=False # <--- Solo los que NO fallaron en auto-radicación
        ).select_related(
            'oficina_clasificada',
            'serie_clasificada',
            'subserie_clasificada'
        ).prefetch_related(
            'adjuntos' # Usar el related_name definido en AdjuntoCorreoEntrante
        ).order_by('-fecha_clasificacion') # Mostrar los más recientes primero
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Correos Pendientes de Radicar (Clasificación IA)"
        # La paginación es manejada automáticamente por ListView con paginate_by
        return context

# --- Vista para Correos que Requieren Revisión Manual ---
class BandejaRevisionManualView(LoginRequiredMixin, EsVentanillaMixin, ListView):
    model = CorreoEntrante
    template_name = 'correspondencia/bandeja_clasificados.html' # Reutilizar plantilla
    context_object_name = 'correos_clasificados' # Mantener nombre de contexto para la plantilla
    # paginate_by = 15 # Quitar paginación del servidor

    def get_queryset(self):
        """Filtra correos procesados, no radicados y que SÍ requieren revisión manual."""
        queryset = CorreoEntrante.objects.filter(
            procesado=True,
            radicado_asociado__isnull=True,
            requiere_revision_manual=True # <--- La diferencia clave
        ).select_related(
            'oficina_clasificada',
            'serie_clasificada',
            'subserie_clasificada'
        ).prefetch_related(
            'adjuntos'
        ).order_by('-fecha_clasificacion')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Correos con Error en Radicación Automática (Revisión Manual)"
        # Añadir un flag para diferenciar en la plantilla si es necesario
        context['es_bandeja_revision'] = True 
        return context

# --- Vista para el Detalle de un Correo Clasificado - DESCOMENTAR ---
class DetalleCorreoClasificadoView(LoginRequiredMixin, EsVentanillaMixin, DetailView):
    model = CorreoEntrante
    template_name = 'correspondencia/detalle_correo_clasificado.html'
    context_object_name = 'correo'

    def get_queryset(self):
        """Asegurar que solo se puedan ver correos procesados y no radicados."""
        return super().get_queryset().filter(
            procesado=True,
            radicado_asociado__isnull=True
        ).prefetch_related('adjuntos') # Cargar adjuntos

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Detalle Correo: {self.object.asunto[:50]}..."
        return context
# --- FIN VISTA DETALLE CORREO ---

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def radicar_correspondencia(request, correo_id=None): # Añadir correo_id opcional
    correo_origen = None
    initial_data = {}

    if correo_id:
        correo_origen = get_object_or_404(CorreoEntrante, pk=correo_id, procesado=True, radicado_asociado__isnull=True)
        # Pre-llenar datos iniciales del formulario
        initial_data = {
            'asunto': correo_origen.asunto,
            'medio_recepcion': 'ELECTRONICO', # Asumir electrónico si viene de correo
            # Intentar encontrar o sugerir contacto basado en remitente
            # 'remitente': encontrar_o_crear_contacto(correo_origen.remitente),
            'oficina_destino': correo_origen.oficina_clasificada,
            'serie': correo_origen.serie_clasificada,
            'subserie': correo_origen.subserie_clasificada,
            # Otros campos que puedas pre-llenar
        }
        # Buscar/Crear contacto (ejemplo simple)
        try:
            # Asumiendo que Contacto tiene un campo 'correo_electronico' único o prioritario
            contacto, created = Contacto.objects.get_or_create(
                correo_electronico=correo_origen.remitente,
                defaults={'entidad': f'Entidad de {correo_origen.remitente}'} # Valor por defecto simple
            )
            initial_data['remitente'] = contacto
        except Exception as e:
            messages.warning(request, f"No se pudo encontrar o crear automáticamente el contacto para {correo_origen.remitente}. Por favor, selecciónelo manualmente. Error: {e}")

    # Pasar initial_data al formulario
    form = CorrespondenciaForm(request.POST or None, initial=initial_data)
    # form_contacto = ContactoForm(request.POST or None, prefix="contacto") # Si tienes form aparte para contacto

    if request.method == 'POST':
        # Validar y guardar como antes...
        if form.is_valid(): # and form_contacto.is_valid():
            try:
                with transaction.atomic():
                    # Crear o usar contacto existente
                    # contacto = form_contacto.save() # O obtenerlo del form principal si está integrado
                    # correspondencia.remitente = contacto
                    correspondencia = form.save(commit=False)
                    correspondencia.usuario_radicador = request.user
                    # Asegúrate que los campos obligatorios estén
                    if not correspondencia.oficina_destino or not correspondencia.serie:
                        messages.error(request, "La Oficina Destino y la Serie son obligatorias.")
                        # Re-renderizar formulario con errores
                        context = {'form': form, 'titulo_pagina': 'Radicar Nueva Correspondencia'}
                        return render(request, 'correspondencia/radicar_form.html', context)

                    correspondencia.save() # Guardar para obtener ID

                    # Crear historial inicial
                    HistorialCorrespondencia.objects.create(
                        correspondencia=correspondencia,
                        evento='RADICADA',
                        usuario=request.user,
                        descripcion=f"Radicada por {request.user.username} desde correo ID {correo_origen.id}" if correo_origen else f"Radicada manualmente por {request.user.username}"
                    )
                    # Marcar el correo origen como radicado
                    if correo_origen:
                        correo_origen.radicado_asociado = correspondencia
                        correo_origen.save(update_fields=['radicado_asociado'])

                        # Opcional: ¿Mover/Copiar adjuntos del CorreoEntrante a AdjuntoCorreo?
                        # for adj_origen in correo_origen.adjuntos.all():
                        #    # Crear nuevo AdjuntoCorreo asociado a la Correspondencia
                        #    pass # Implementar lógica de copia si es necesario

                    messages.success(request, f"Correspondencia {correspondencia.numero_radicado} radicada exitosamente.")
                    # Redirigir a la lista de pendientes, que es la acción siguiente para Ventanilla
                    return redirect('correspondencia:pendientes_distribuir') 

            except Exception as e:
                messages.error(request, f"Error al radicar la correspondencia: {e}")
                # Considera loggear el error completo: logger.error(f"Error radicando: {e}", exc_info=True)

        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")

    # Renderizar formulario GET o si hubo error POST
    context = {
        'form': form,
        # 'form_contacto': form_contacto,
        'titulo_pagina': 'Radicar Nueva Correspondencia' + (f" (Desde Correo ID: {correo_id})" if correo_id else ""),
        'correo_origen': correo_origen # Pasar el correo origen para mostrar info si se quiere
    }
    return render(request, 'correspondencia/radicar_form.html', context)

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def lista_pendientes_distribuir(request):
    """Muestra la lista de correspondencia radicada pendiente de asignar a usuario."""
    
    # Filtrar correspondencia únicamente en estado RADICADA
    items_a_mostrar = Correspondencia.objects.filter(
        estado='RADICADA' # Solo mostrar las que necesitan acción
    ).select_related(
        'oficina_destino', 
        'usuario_radicador' 
    ).order_by('-fecha_radicacion') # Mostrar más recientes primero
    
    context = {
        'correspondencias': items_a_mostrar,
        'titulo_pagina': 'Correspondencia Pendiente de Asignar' # Título más específico
    }
    return render(request, 'correspondencia/lista_pendientes.html', context)

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def distribuir_correspondencia(request, pk):
    """Distribuye una correspondencia a un usuario específico y crea el registro inicial de distribución."""
    correspondencia = get_object_or_404(Correspondencia, pk=pk)
    
    # Obtener usuarios de la oficina destino (con perfil asociado)
    usuarios_oficina = User.objects.filter(
        perfil__oficina=correspondencia.oficina_destino
    ).select_related('perfil') # Incluir perfil para asegurar que existe
    
    if request.method == 'POST':
        usuario_id = request.POST.get('usuario')
        observaciones = request.POST.get('observaciones', 'Asignación inicial desde Ventanilla') # Observación por defecto
        
        if not usuario_id:
             messages.error(request, "Debe seleccionar un usuario.")
             # Re-renderizar con error
             context = {
                 'correspondencia': correspondencia,
                 'usuarios_oficina': usuarios_oficina,
                 'titulo_pagina': 'Asignar Correspondencia a Usuario'
             }
             return render(request, 'correspondencia/distribuir_correspondencia.html', context)

        try:
            usuario_destino = User.objects.get(id=usuario_id)
            # Verificar que el usuario pertenece a la oficina destino (doble chequeo)
            if not hasattr(usuario_destino, 'perfil') or usuario_destino.perfil.oficina != correspondencia.oficina_destino:
                messages.error(request, "El usuario seleccionado no pertenece a la oficina destino o no tiene perfil.")
                return redirect('correspondencia:distribuir_correspondencia', pk=pk)
            
            with transaction.atomic():
                # 1. Actualizar la correspondencia
                correspondencia.usuario_destino_inicial = usuario_destino
                correspondencia.estado = 'ASIGNADA_USUARIO'
                correspondencia.save(update_fields=['usuario_destino_inicial', 'estado'])
                
                # 2. Crear el registro de DistribucionInternaUsuario para el asignado inicial
                # Esto centraliza el seguimiento de quién debe verla y si la ha leído.
                distribucion_inicial, created = DistribucionInternaUsuario.objects.update_or_create(
                    correspondencia=correspondencia,
                    usuario_asignado=usuario_destino,
                    defaults={
                        'asignado_por': request.user, # Quién hizo la asignación (ventanilla)
                        'fecha_asignacion': timezone.now(),
                        'observaciones': observaciones,
                        'leido': False # Inicialmente no leído
                    }
                )
                
                # 3. Registrar en el historial general
                HistorialCorrespondencia.objects.create(
                    correspondencia=correspondencia,
                    evento='ASIGNADA_USUARIO',
                    usuario=request.user,
                    descripcion=f"Asignada a {usuario_destino.get_full_name() or usuario_destino.username}"
                )
            
            messages.success(request, f'Correspondencia {correspondencia.numero_radicado} asignada exitosamente a {usuario_destino.get_full_name() or usuario_destino.username}')
            return redirect('correspondencia:pendientes_distribuir')
            
        except User.DoesNotExist:
            messages.error(request, "Usuario seleccionado no válido.")
        except Exception as e:
            messages.error(request, f"Error al asignar la correspondencia: {str(e)}")
            # Considerar loggear el error completo
    
    # Contexto para el método GET
    context = {
        'correspondencia': correspondencia,
        'usuarios_oficina': usuarios_oficina,
        'titulo_pagina': 'Asignar Correspondencia a Usuario'
    }
    return render(request, 'correspondencia/distribuir_correspondencia.html', context)

# --- Vistas para Contactos --- 

@login_required
# @permission_required('correspondencia.view_contacto', raise_exception=True) # Permiso opcional
def listar_contactos(request):
    """Muestra una lista paginada de todos los contactos externos, incluyendo su entidad."""
    # Optimizar consulta incluyendo la entidad externa relacionada
    contactos_list = Contacto.objects.select_related('entidad_externa').all()
    
    # Búsqueda simple por nombre, apellido, correo o entidad
    query = request.GET.get('q')
    if query:
        contactos_list = contactos_list.filter(
            Q(nombres__icontains=query) | 
            Q(apellidos__icontains=query) | 
            Q(correo_electronico__icontains=query) |
            Q(entidad_externa__nombre__icontains=query) # Buscar por nombre de entidad
        )
    
    paginator = Paginator(contactos_list, 25) # 25 contactos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'contactos': page_obj,
        'titulo_pagina': 'Gestionar Contactos Externos',
        'search_query': query or "" # Pasar query a la plantilla para mostrarlo en el input
    }
    return render(request, 'correspondencia/lista_contactos.html', context)

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def crear_contacto(request):
    """Crea un nuevo Contacto Externo (ahora requiere seleccionar EntidadExterna)."""
    if request.method == 'POST':
        # Usar ContactoForm actualizado
        form = ContactoForm(request.POST)
        if form.is_valid():
            try:
                contacto = form.save()
                messages.success(request, f"Contacto '{contacto.nombre_completo}' de la entidad '{contacto.entidad_externa.nombre}' creado exitosamente.")
                return redirect('correspondencia:listar_contactos') # Redirigir a la lista
            except Exception as e:
                 messages.error(request, f"Error al crear el contacto: {e}")
        else:
             messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        # GET: mostrar formulario vacío
        form = ContactoForm()
    
    context = {
        'form': form,
        'titulo_pagina': 'Crear Nuevo Contacto Externo'
    }
    # Reutilizar plantilla de formulario genérica o crear una específica
    return render(request, 'correspondencia/contacto_form.html', context)

@login_required
def home_view(request):
    # ... existing code ...
    return render(request, 'correspondencia/lista_pendientes.html', context)

@login_required
def ver_perfil(request):
    # ... existing code ...
    return render(request, 'correspondencia/lista_pendientes.html', context)

@login_required
def bandeja_entrada(request):
    """Muestra la correspondencia asignada directamente o compartida con el usuario."""
    usuario_actual = request.user
    perfil_usuario = getattr(usuario_actual, 'perfil', None)
    nombre_oficina = "Oficina no asignada"
    correspondencias_list = Correspondencia.objects.none() # Queryset vacío por defecto
    load_success = False

    if perfil_usuario and perfil_usuario.oficina:
        nombre_oficina = perfil_usuario.oficina.nombre
        try:
            # 1. Correspondencia asignada directamente al usuario
            directamente_asignada = Q(usuario_destino_inicial=usuario_actual)
            
            # 2. Correspondencia compartida con el usuario a través de DistribucionInternaUsuario
            compartida_con_usuario = Q(distribuciones_internas__usuario_asignado=usuario_actual)
            
            # Combinar ambos filtros con OR
            correspondencias_list = Correspondencia.objects.filter(
                directamente_asignada | compartida_con_usuario,
                oficina_destino=perfil_usuario.oficina # Asegurar que sea de su oficina
            ).distinct().select_related(
                'remitente', 
                'oficina_destino',
                'usuario_destino_inicial' # Puede ser útil mostrar quién fue el asignado inicial
            ).prefetch_related(
                'adjuntos_correo', # Para mostrar adjuntos si es necesario
                'distribuciones_internas' # Para posible lógica adicional
            ).order_by('-fecha_radicacion') # O por fecha de asignación/compartido?

            load_success = True
            print(f"Usuario: {usuario_actual}, Oficina: {nombre_oficina}, Correspondencias encontradas: {correspondencias_list.count()}")

        except AttributeError as e:
             print(f"Error de atributo en bandeja_entrada (posiblemente perfil): {e}")
             messages.error(request, "Error al cargar datos de usuario/oficina.")
             # load_success permanece False
        except Exception as e:
            print(f"Error capturado en bandeja_entrada: {e}")
            messages.error(request, f"Ocurrió un error inesperado al cargar la bandeja: {e}")
            # load_success permanece False
    else:
        messages.warning(request, "No tienes un perfil o una oficina asignada para ver tu bandeja de entrada.")
        # load_success permanece False

    # Configurar el contexto final
    context = {
        'titulo_pagina': f"Bandeja de Entrada - {nombre_oficina}",
        'correspondencias': correspondencias_list, 
        'nombre_oficina': nombre_oficina,
        'load_success': load_success
    }

    print("Contexto antes de render:", context)
    return render(request, 'correspondencia/bandeja_entrada.html', context)

@login_required
def detalle_correspondencia(request, pk):
    """Muestra los detalles de una correspondencia radicada y la marca como leída automáticamente al primer acceso autorizado."""
    correspondencia = get_object_or_404(
        Correspondencia.objects.select_related(
            'remitente', 'oficina_destino', 'serie', 'subserie', 'usuario_radicador' 
        ).prefetch_related(
             'adjuntos_correo', # Usar related_name correcto
             'historial__usuario', # Optimizar historial
             'distribuciones_internas__usuario_asignado' # Para verificar si fue compartido
        ), 
        pk=pk
    )
    titulo_pagina = f"Detalle Radicado: {correspondencia.numero_radicado}"
    usuario_actual = request.user

    # --- Lógica de Permisos para VER --- 
    puede_ver = False
    is_ventanilla_or_admin = usuario_actual.groups.filter(name__in=['Ventanilla', 'Admin']).exists() or usuario_actual.is_superuser
    perfil_usuario = getattr(usuario_actual, 'perfil', None)
    es_de_oficina_destino = perfil_usuario and perfil_usuario.oficina == correspondencia.oficina_destino
    es_asignado_inicial = correspondencia.usuario_destino_inicial == usuario_actual
    fue_compartido_con_usuario = DistribucionInternaUsuario.objects.filter(correspondencia=correspondencia, usuario_asignado=usuario_actual).exists()

    if es_de_oficina_destino or correspondencia.usuario_radicador == usuario_actual or is_ventanilla_or_admin or fue_compartido_con_usuario:
        puede_ver = True

    if not puede_ver:
         messages.error(request, "No tienes permiso para ver esta correspondencia.")
         # Determinar a dónde redirigir: si tiene perfil a bandeja_personal, sino a welcome?
         redirect_url = 'correspondencia:bandeja_personal' if perfil_usuario else 'correspondencia:welcome' 
         return redirect(redirect_url)

    # --- Lógica para Marcar como Leído Automáticamente --- 
    # Busca la distribución específica para este usuario y marca su flag 'leido'
    if es_de_oficina_destino and correspondencia.estado != 'RADICADA': # No marcar si solo está radicada
        distribucion_usuario = None
        try:
            # Buscar la entrada de distribución para el usuario actual
            distribucion_usuario = DistribucionInternaUsuario.objects.get(
                correspondencia=correspondencia, 
                usuario_asignado=usuario_actual
            )
            # Si existe y aún no está marcada como leída por este usuario
            if not distribucion_usuario.leido:
                distribucion_usuario.leido = True
                distribucion_usuario.save(update_fields=['leido'])
                
                # Opcional: Actualizar estado general y historial la primera vez que *alguien* la lee
                # Contar cuántos la han leído ahora
                leidos_count = DistribucionInternaUsuario.objects.filter(correspondencia=correspondencia, leido=True).count()
                
                if leidos_count == 1 and correspondencia.estado != 'LEIDA': # Si es el PRIMERO en leerla y no está ya 'LEIDA'
                     try:
                         with transaction.atomic():
                            correspondencia.estado = 'LEIDA'
                            correspondencia.leido_por_oficina = True # Mantenemos este flag como indicador general
                            correspondencia.save(update_fields=['estado', 'leido_por_oficina'])
                            
                            HistorialCorrespondencia.objects.create(
                                correspondencia=correspondencia, evento='LEIDA', usuario=usuario_actual,
                                descripcion=f"Leída por primera vez por {usuario_actual.username}."
                            )
                     except Exception as e:
                         messages.error(request, f"Error al actualizar estado general a LEIDA: {e}")

        except DistribucionInternaUsuario.DoesNotExist:
             # No se encontró registro de distribución para este usuario (caso raro si tiene permiso)
             # Podríamos loggear esto o simplemente ignorarlo.
             pass 
        except Exception as e:
            messages.error(request, f"Error al intentar marcar la distribución como leída: {e}")
            # Considerar loggear

    # --- Lógica de Permisos para COMPARTIR --- 
    puede_compartir = False
    # El usuario debe pertenecer a la oficina y ser el asignado inicial o alguien a quien se compartió
    if es_de_oficina_destino and (es_asignado_inicial or fue_compartido_con_usuario):
        puede_compartir = True
    # Opcional: Permitir a Ventanilla/Admin compartir siempre (si tienen oficina)
    # elif is_ventanilla_or_admin and perfil_usuario and perfil_usuario.oficina:
    #     puede_compartir = True
        
    # --- Lógica de Permisos para RESPONDER --- 
    puede_responder = False
    if es_de_oficina_destino and (es_asignado_inicial or fue_compartido_con_usuario):
        puede_responder = True
    # Podríamos añadir otras condiciones si fueran necesarias

    # Obtener historial y adjuntos (ya precargados)
    historial = correspondencia.historial.all()
    adjuntos = correspondencia.adjuntos_correo.all()

    # Obtener la lista de usuarios que han leído (filtrando desde las distribuciones)
    usuarios_que_leyeron = User.objects.filter(
        correspondencia_asignada__correspondencia=correspondencia,
        correspondencia_asignada__leido=True
    ).distinct()

    context = {
        'titulo_pagina': titulo_pagina,
        'correspondencia': correspondencia,
        'historial': historial,
        'adjuntos': adjuntos,
        'puede_compartir': puede_compartir, # Para mostrar/ocultar botón Compartir
        'puede_responder': puede_responder, # <--- Añadir esta variable al contexto
        'usuarios_que_leyeron': usuarios_que_leyeron # Pasar la lista al template
    }
    return render(request, 'correspondencia/detalle_correspondencia.html', context)

# --- Vista para marcar leído (AHORA REDUNDANTE, SE PUEDE ELIMINAR O COMENTAR) ---
# @login_required
# def marcar_como_leido(request, pk):
#     # ... (código anterior) ...
#     pass # Mantener comentado o eliminar

@login_required
def redistribuir_interna(request, pk):
    """Permite redistribuir una correspondencia a usuarios dentro de la misma oficina."""
    correspondencia = get_object_or_404(Correspondencia, pk=pk)
    
    # Verificar que el usuario pertenece a la oficina destino
    if not request.user.perfil.oficina == correspondencia.oficina_destino:
        messages.error(request, "No tienes permiso para redistribuir esta correspondencia.")
        return redirect('bandeja_entrada')
    
    # Obtener usuarios de la misma oficina
    usuarios_oficina = User.objects.filter(
        perfil__oficina=correspondencia.oficina_destino
    ).exclude(
        id=request.user.id  # Excluir al usuario actual
    )
    
    if request.method == 'POST':
        usuario_id = request.POST.get('usuario')
        observaciones = request.POST.get('observaciones', '')
        
        try:
            usuario = User.objects.get(id=usuario_id)
            # Crear la distribución interna
            DistribucionInternaUsuario.objects.create(
                correspondencia=correspondencia,
                usuario_asignado=usuario,
                asignado_por=request.user,
                observaciones=observaciones
            )
            
            # Registrar en el historial
            HistorialCorrespondencia.objects.create(
                correspondencia=correspondencia,
                evento='REDISTRIBUIDA_INTERNA',
                usuario=request.user,
                descripcion=f"Redistribuida internamente a {usuario.get_full_name() or usuario.username}"
            )
            
            messages.success(request, f'Correspondencia redistribuida exitosamente a {usuario.get_full_name() or usuario.username}')
            return redirect('bandeja_entrada')
            
        except User.DoesNotExist:
            messages.error(request, "Usuario seleccionado no válido.")
        except Exception as e:
            messages.error(request, f"Error al redistribuir: {str(e)}")
    
    context = {
        'correspondencia': correspondencia,
        'usuarios_oficina': usuarios_oficina,
        'titulo_pagina': 'Redistribuir Correspondencia'
    }
    return render(request, 'correspondencia/redistribuir_interna.html', context)

@login_required
def compartir_correspondencia(request, pk):
    """Permite a un usuario compartir una correspondencia con otros de su oficina."""
    correspondencia = get_object_or_404(Correspondencia, pk=pk)
    usuario_actual = request.user
    perfil_usuario_actual = getattr(usuario_actual, 'perfil', None)

    # --- Verificación de Permisos para Compartir ---
    puede_compartir = False
    # 1. ¿Es el destinatario inicial?
    if correspondencia.usuario_destino_inicial == usuario_actual:
        puede_compartir = True
    # 2. ¿Se la compartieron previamente?
    elif DistribucionInternaUsuario.objects.filter(correspondencia=correspondencia, usuario_asignado=usuario_actual).exists():
        puede_compartir = True
    # 3. ¿Es de Ventanilla o Superuser? (Podrían compartir también? Definir reglas)
    # Por ahora, solo el destinatario inicial o alguien a quien se compartió puede compartir.

    if not puede_compartir:
        messages.error(request, "No tienes permiso para compartir esta correspondencia.")
        return redirect('correspondencia:detalle_correspondencia', pk=pk)

    # Asegurarse de que el usuario tenga perfil y oficina
    if not perfil_usuario_actual or not perfil_usuario_actual.oficina:
        messages.error(request, "No tienes una oficina asignada para poder compartir.")
        return redirect('correspondencia:detalle_correspondencia', pk=pk)

    oficina_usuario = perfil_usuario_actual.oficina

    # --- Lógica del Formulario ---
    if request.method == 'POST':
        form = CompartirCorrespondenciaForm(request.POST, oficina=oficina_usuario, usuario_actual=usuario_actual)
        if form.is_valid():
            usuarios_a_compartir = form.cleaned_data['usuarios']
            observaciones = form.cleaned_data['observaciones']
            
            usuarios_compartidos_count = 0
            for usuario in usuarios_a_compartir:
                # Doble chequeo: ¿Pertenece a la misma oficina?
                if getattr(usuario, 'perfil', None) and usuario.perfil.oficina == oficina_usuario:
                    # Evitar compartir consigo mismo o duplicados
                    if usuario != usuario_actual and not DistribucionInternaUsuario.objects.filter(correspondencia=correspondencia, usuario_asignado=usuario).exists():
                        DistribucionInternaUsuario.objects.create(
                            correspondencia=correspondencia,
                            usuario_asignado=usuario,
                            asignado_por=usuario_actual,
                            observaciones=observaciones
                        )
                        # Registrar en historial general
                        HistorialCorrespondencia.objects.create(
                            correspondencia=correspondencia,
                            evento='REDISTRIBUIDA_INTERNA', # Usamos este estado para "Compartir"
                            usuario=usuario_actual,
                            descripcion=f"Compartida con {usuario.get_full_name() or usuario.username}. Obs: {observaciones[:100]}"
                        )
                        usuarios_compartidos_count += 1
                else:
                     messages.warning(request, f"El usuario {usuario.username} no pertenece a tu oficina y no se compartió.")

            if usuarios_compartidos_count > 0:
                 messages.success(request, f"Correspondencia compartida exitosamente con {usuarios_compartidos_count} usuario(s).")
                 # Actualizar estado principal si se desea (opcional)
                 # correspondencia.estado = 'REDISTRIBUIDA_INTERNA' 
                 # correspondencia.save()
            else:
                 messages.info(request, "No se compartió con ningún usuario nuevo (posiblemente ya estaba compartido o no eran de la oficina).")
                 
            return redirect('correspondencia:detalle_correspondencia', pk=pk)
        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        # Pasar la oficina y el usuario actual al form para filtrar queryset
        form = CompartirCorrespondenciaForm(oficina=oficina_usuario, usuario_actual=usuario_actual)

    context = {
        'titulo_pagina': f'Compartir Radicado: {correspondencia.numero_radicado}',
        'correspondencia': correspondencia,
        'form': form
    }
    return render(request, 'correspondencia/compartir_form.html', context)

@login_required
@user_passes_test(lambda u: not u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:pendientes_distribuir') # Redirigir Ventanilla
def bandeja_personal(request):
    """Muestra la bandeja personal del usuario (asignada + compartida) con estado de lectura X/Y y plazo."""
    usuario_actual = request.user
    perfil_usuario = getattr(usuario_actual, 'perfil', None)
    correspondencias_list = [] 
    load_success = False

    if perfil_usuario and perfil_usuario.oficina:
        try:
            # IDs de correspondencia compartidas directamente con el usuario actual
            compartida_con_usuario_ids = list(DistribucionInternaUsuario.objects.filter(
                usuario_asignado=usuario_actual
            ).values_list('correspondencia_id', flat=True))

            # Queryset base: asignada directamente O compartida con el usuario Y de su oficina
            correspondencias_qs = Correspondencia.objects.filter(
                (Q(usuario_destino_inicial=usuario_actual) | Q(pk__in=compartida_con_usuario_ids)),
                oficina_destino=perfil_usuario.oficina
            ).distinct()
            
            # Anotar el queryset para obtener conteos de lectura
            correspondencias_qs = correspondencias_qs.annotate(
                # Contar total de distribuciones (Y)
                total_destinatarios=Count('distribuciones_internas', distinct=True),
                # Contar distribuciones marcadas como leídas (X)
                total_leidos=Count('distribuciones_internas', filter=Q(distribuciones_internas__leido=True), distinct=True),
                 # Marcar si el usuario actual ya lo leyó (para la interfaz)
                 leido_por_usuario_actual=Case(
                     When(distribuciones_internas__usuario_asignado=usuario_actual, distribuciones_internas__leido=True, then=True),
                     default=False,
                     output_field=BooleanField()
                 )
            )

            # Optimizar relaciones relacionadas después de anotar
            correspondencias_qs = correspondencias_qs.select_related(
                'remitente', 'oficina_destino', 'usuario_destino_inicial'
            ).prefetch_related(
                'adjuntos_correo'
                # 'distribuciones_internas__asignado_por', # Ya no son estrictamente necesarias aquí con los counts
                # 'distribuciones_internas__usuario_asignado' 
            ).order_by('-fecha_radicacion')

            # La lista final ahora es directamente el queryset anotado
            correspondencias_list = list(correspondencias_qs) # Convertir a lista para evitar re-evaluación
            load_success = True
            
        except Exception as e:
            print(f"Error crítico cargando bandeja personal {usuario_actual.username}: {e}")
            messages.error(request, f"Ocurrió un error inesperado al cargar tu bandeja: {e}")
            load_success = False
    else:
        messages.warning(request, "No tienes un perfil o una oficina asignada para ver tu bandeja.")
        load_success = False

    context = {
        'page_title': 'Bandeja Personal',
        'correspondencias': correspondencias_list, # Ya tiene 'total_leidos' y 'total_destinatarios'
        'load_success': load_success,
        'mostrar_boton_compartir': True, # O basarlo en permisos si es necesario
        'tipo_tabla': 'personal'
    }
    return render(request, 'correspondencia/bandeja_personal.html', context)

@login_required
@user_passes_test(lambda u: not u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:pendientes_distribuir') # Corregido previamente
def bandeja_oficina(request):
    """Muestra la correspondencia que ha sido compartida dentro de la oficina del usuario, con estado de lectura y plazo."""
    usuario_actual = request.user
    perfil_usuario = getattr(usuario_actual, 'perfil', None)
    correspondencias_list = []
    load_success = False
    nombre_oficina = "Desconocida"

    if perfil_usuario and perfil_usuario.oficina:
        nombre_oficina = perfil_usuario.oficina.nombre
        try:
            # Filtrar correspondencia de la oficina del usuario que tenga al menos una distribución interna.
            correspondencias_qs = Correspondencia.objects.filter(
                oficina_destino=perfil_usuario.oficina,
                distribuciones_internas__isnull=False # Asegura que haya sido compartida al menos una vez
            ).distinct()
            
            # Anotar el queryset para obtener conteos de lectura
            correspondencias_qs = correspondencias_qs.annotate(
                total_destinatarios=Count('distribuciones_internas', distinct=True),
                total_leidos=Count('distribuciones_internas', filter=Q(distribuciones_internas__leido=True), distinct=True)
                # No necesitamos 'leido_por_usuario_actual' aquí, ya que la bandeja de oficina es general
            )
            
            # Optimizar relaciones relacionadas después de anotar
            correspondencias_qs = correspondencias_qs.select_related(
                'remitente', 'oficina_destino', 'usuario_destino_inicial'
            ).prefetch_related(
                'adjuntos_correo' 
                # Las relaciones de distribución ya no son estrictamente necesarias aquí
            ).order_by('-fecha_radicacion')
            
            # Preparar lista final (ahora es el queryset anotado)
            correspondencias_list = list(correspondencias_qs) 
                
            load_success = True
        except Exception as e:
            print(f"Error crítico cargando bandeja oficina {nombre_oficina}: {e}")
            messages.error(request, f"Ocurrió un error inesperado al cargar la bandeja de la oficina: {e}")
            load_success = False
    else:
        messages.warning(request, "No tienes un perfil o una oficina asignada para ver la bandeja de oficina.")
        load_success = False

    context = {
        'page_title': f'Bandeja Oficina (Compartidos): {nombre_oficina}',
        'correspondencias': correspondencias_list, # Ya incluye los counts
        'load_success': load_success,
        'mostrar_boton_compartir': False, 
        'tipo_tabla': 'oficina'
    }
    return render(request, 'correspondencia/bandeja_oficina.html', context)

# === VISTAS PARA VENTANILLA - RADICACIÓN MANUAL DE CORREOS ===

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def bandeja_correos_pendientes_view(request):
    """Muestra la lista de TODOS los correos electrónicos entrantes, indicando su estado de radicación."""
    # Quitar el filtro radicado_asociado__isnull=True para mostrar todos
    todos_los_correos = CorreoEntrante.objects.select_related(
        'radicado_asociado' # Incluir para verificar estado y obtener número si existe
    ).prefetch_related(
        'adjuntos' 
    ).order_by('-fecha_lectura_imap')

    paginator = Paginator(todos_los_correos, 25) # 25 correos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'correos': page_obj, 
        'titulo_pagina': 'Gestión de Correos Entrantes' # Título más general
    }
    return render(request, 'correspondencia/bandeja_correos_pendientes.html', context)

# ------------- ENDPOINT AJAX PARA SUBSERIES -------------
@require_GET
def api_subseries(request):
    """
    Endpoint AJAX que devuelve {id, nombre} de SubserieDocumental
    filtradas por serie_id.
    """
    serie_id = request.GET.get("serie_id")
    if serie_id:
        try:
            # Validar que serie_id sea un número entero
            serie_id = int(serie_id)
            qs = SubserieDoc.objects.filter(serie_id=serie_id).order_by('nombre')
            data = list(qs.values("id", "nombre"))
        except (ValueError, TypeError):
            # Si serie_id no es válido, devolver lista vacía
            data = []
    else:
        data = []
    return JsonResponse(data, safe=False)

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(),
                 login_url='correspondencia:welcome')
def detalle_correo_entrante_view(request, correo_id):
    """
    Muestra el detalle completo de un CorreoEntrante y permite:
     - Crear un Contacto desde un modal
     - Radicar manualmente el correo (otro modal)
    """
    correo = get_object_or_404(
        CorreoEntrante.objects.prefetch_related('adjuntos'),
        pk=correo_id
    )
    titulo_pagina = f'Detalle Correo: {correo.asunto[:50]}...'

    # Formulario de contacto (usará el prefijo 'contacto')
    form_contacto = ContactoForm(request.POST or None, prefix="contacto")

    # Formulario de radicación (solo si NO está radicado aún, prefijo 'radicar')
    form_radicacion = None
    if not correo.radicado_asociado:
        # Intentar encontrar un contacto existente basado en el email del remitente
        contacto_sugerido = Contacto.objects.filter(
            correo_electronico__iexact=correo.remitente
        ).first()

        # Datos iniciales para el formulario de radicación
        initial_radicacion = {
            'asunto': correo.asunto,
            'medio_recepcion': 'ELECTRONICO', # Asumimos electrónico
            'remitente': contacto_sugerido, # Preseleccionar si se encontró
            # Podrías añadir aquí las clasificaciones de IA si existen en el correo
            # 'oficina_destino': correo.oficina_clasificada,
            # 'serie': correo.serie_clasificada,
            # 'subserie': correo.subserie_clasificada,
        }

        # Instanciar el formulario de radicación
        # Pasamos 'data' solo si es POST y el prefijo coincide, sino usamos 'initial' en GET
        form_radicacion = ManualRadicacionCorreoForm(
            data=request.POST if request.method == 'POST' and request.POST.get('form_prefix') == 'radicar' else None,
            initial=initial_radicacion if request.method == 'GET' else None,
            prefix="radicar" # Muy importante para diferenciar formularios
        )

        # --- Lógica para actualizar queryset de subserie (similar al __init__ del form) ---
        serie_id = None
        # Si viene de POST (y es este formulario)
        if request.method == 'POST' and request.POST.get('form_prefix') == 'radicar':
            serie_id = request.POST.get('radicar-serie')
        # Si es GET y hay una serie inicial
        elif request.method == 'GET' and form_radicacion.initial.get('serie'):
            serie_id = form_radicacion.initial.get('serie').pk
        # Si es GET y no hay serie inicial (quizás prellenada por IA)
        elif request.method == 'GET' and 'serie' in initial_radicacion and initial_radicacion['serie']:
             serie_id = initial_radicacion['serie'].pk

        if serie_id:
            try:
                form_radicacion.fields['subserie'].queryset = (
                    SubserieDoc.objects.filter(serie_id=int(serie_id)).order_by('nombre')
                )
                form_radicacion.fields['subserie'].disabled = False
            except (ValueError, TypeError):
                 form_radicacion.fields['subserie'].queryset = SubserieDoc.objects.none()
                 form_radicacion.fields['subserie'].disabled = True
        else:
            form_radicacion.fields['subserie'].queryset = SubserieDoc.objects.none()
            form_radicacion.fields['subserie'].disabled = True
        # --- Fin lógica subserie ---

    # === Procesamiento POST ===
    if request.method == 'POST':
        # Identificar qué formulario se envió usando un campo oculto o el nombre del botón
        form_prefix = request.POST.get('form_prefix')

        # --- 1) Intento de Crear Contacto --- 
        if form_prefix == 'contacto':
            form_contacto = ContactoForm(request.POST, prefix="contacto") # Re-instanciar con POST data
            if form_contacto.is_valid():
                try:
                    nuevo_contacto = form_contacto.save()
                    messages.success(request, f"Contacto '{nuevo_contacto}' creado exitosamente.")
                    # Redirigir a la misma página para limpiar el POST y ver el mensaje
                    return redirect('correspondencia:detalle_correo_entrante', correo_id=correo.id)
                except IntegrityError as e:
                    # Manejar error de constraint único (ej. email duplicado si es único)
                    error_msg = f"Error al crear contacto: Ya existe un contacto similar o con ese correo. {e}"
                    # Tratar de identificar el campo problemático si es posible
                    if 'contacto_unico_por_entidad' in str(e):
                         error_msg = "Error: Ya existe un contacto con esos nombres y correo para esa entidad."
                    elif 'correo_electronico' in str(e):
                         error_msg = "Error: Ya existe un contacto con ese correo electrónico."
                    messages.error(request, error_msg)
                except Exception as e:
                    messages.error(request, f"Error inesperado al crear contacto: {e}")
            else:
                # El formulario de contacto no es válido, los errores se mostrarán en el modal
                messages.error(request, "Por favor corrija los errores en el formulario de contacto.")
                # No redirigir, mantener los datos POST para mostrar errores
                # Asegurarse que el modal se muestre con los errores (requiere JS o flag en contexto)
                # Añadiremos un flag al contexto para indicar que el modal de contacto debe abrirse
                # context['open_contacto_modal'] = True # Lo añadiremos al contexto final

        # --- 2) Intento de Radicar Correo --- 
        elif form_prefix == 'radicar' and form_radicacion:
            form_radicacion = ManualRadicacionCorreoForm(request.POST, prefix="radicar") # Re-instanciar con POST data
            if form_radicacion.is_valid():
                try:
                    with transaction.atomic():
                        # Crear la Correspondencia
                        correspondencia = form_radicacion.save(commit=False)
                        correspondencia.medio_recepcion   = 'ELECTRONICO' # Forzar medio
                        correspondencia.usuario_radicador = request.user
                        # El estado por defecto es 'RADICADA' según el modelo
                        # correspondencia.estado = 'RADICADA'
                        correspondencia.save() # Guardar para obtener ID y generar número_radicado

                        # Crear historial inicial
                        HistorialCorrespondencia.objects.create(
                            correspondencia=correspondencia,
                            evento='RADICADA',
                            usuario=request.user,
                            descripcion=(
                                f"Radicada manualmente por {request.user.username} "
                                f"desde CorreoEntrante ID {correo.id}"
                            )
                        )

                        # Asociar la correspondencia creada al correo original
                        correo.radicado_asociado = correspondencia
                        correo.save(update_fields=['radicado_asociado'])

                        # Copiar adjuntos del CorreoEntrante a AdjuntoCorreo
                        for adj_origen in correo.adjuntos.all():
                            # Crear una instancia del nuevo modelo de adjunto
                            adj_destino = AdjuntoCorreo(
                                correspondencia=correspondencia, # Asociar al nuevo radicado
                                nombre_original=adj_origen.nombre_original,
                                tipo_mime=adj_origen.tipo_mime
                            )
                            # Copiar el contenido del archivo
                            if adj_origen.archivo:
                                try:
                                    # Leer contenido y guardarlo en el nuevo campo FileField
                                    file_content = ContentFile(adj_origen.archivo.read())
                                    # Usar nombre original para guardar el archivo
                                    file_name = adj_origen.nombre_original or os.path.basename(adj_origen.archivo.name)
                                    adj_destino.archivo.save(file_name, file_content, save=False) # save=False porque guardaremos el modelo adj_destino
                                except Exception as e:
                                    print(f"Error copiando archivo adjunto {adj_origen.id}: {e}")
                                    # Considerar añadir un mensaje de advertencia
                                    messages.warning(request, f"No se pudo copiar el adjunto: {adj_origen.nombre_original}")
                            # Guardar el nuevo adjunto asociado a la correspondencia
                            adj_destino.save()

                        messages.success(
                            request,
                            f"Correo radicado exitosamente como {correspondencia.numero_radicado}."
                        )
                        # Redirigir a la bandeja de correos pendientes después de radicar
                        return redirect('correspondencia:bandeja_correos_pendientes')

                except IntegrityError as e:
                    messages.error(request, f"Error de integridad al radicar: {e}")
                    traceback.print_exc() # Loggear el traceback completo para depuración
                except Exception as e:
                    messages.error(request, f"Error interno inesperado al radicar: {e}")
                    traceback.print_exc()
            else:
                # El formulario de radicación no es válido
                messages.error(request, "Por favor corrija los errores en el formulario de radicación.")
                # No redirigir, mantener datos POST para mostrar errores en el modal
                # Añadiremos un flag al contexto para indicar que el modal de radicación debe abrirse
                # context['open_radicacion_modal'] = True # Lo añadiremos al contexto final

    # === Preparación del Contexto para GET o si hubo error en POST ===
    context = {
        'correo': correo,
        'form_contacto': form_contacto,
        'form_radicacion': form_radicacion, # Puede ser None si ya está radicado
        'titulo_pagina': titulo_pagina,
        'open_contacto_modal': request.method == 'POST' and request.POST.get('form_prefix') == 'contacto' and not form_contacto.is_valid(),
        'open_radicacion_modal': request.method == 'POST' and request.POST.get('form_prefix') == 'radicar' and form_radicacion and not form_radicacion.is_valid(),
    }

    return render(
        request,
        'correspondencia/detalle_correo_entrante.html',
        context
    )
# === FIN VISTAS VENTANILLA ===

# === CRUD Entidades Externas (NUEVO) ===

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def listar_entidades(request):
    """Muestra una lista paginada de todas las Entidades Externas."""
    entidades_list = EntidadExterna.objects.all()
    # Podríamos añadir búsqueda aquí si es necesario en el futuro
    # query = request.GET.get('q')
    # if query:
    #     entidades_list = entidades_list.filter(nombre__icontains=query)
    
    paginator = Paginator(entidades_list, 25) # 25 entidades por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'entidades': page_obj,
        'titulo_pagina': 'Gestionar Entidades Externas'
    }
    return render(request, 'correspondencia/lista_entidades.html', context)

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def crear_entidad(request):
    """Crea una nueva Entidad Externa."""
    if request.method == 'POST':
        form = EntidadExternaForm(request.POST)
        if form.is_valid():
            try:
                entidad = form.save()
                messages.success(request, f"Entidad '{entidad.nombre}' creada exitosamente.")
                return redirect('correspondencia:listar_entidades') # Redirigir a la lista
            except Exception as e:
                 messages.error(request, f"Error al crear la entidad: {e}")
        else:
             messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = EntidadExternaForm()
    
    context = {
        'form': form,
        'titulo_pagina': 'Crear Nueva Entidad Externa'
    }
    return render(request, 'correspondencia/entidad_form.html', context)

# Aquí podríamos añadir vistas para editar_entidad y eliminar_entidad en el futuro.

# === FIN CRUD Entidades Externas ===

# === CRUD Contactos (Ajustado para EntidadExterna) ===
@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def listar_contactos(request):
    """Muestra una lista paginada de todos los contactos externos, incluyendo su entidad."""
    # Optimizar consulta incluyendo la entidad externa relacionada
    contactos_list = Contacto.objects.select_related('entidad_externa').all()
    
    # Búsqueda simple por nombre, apellido, correo o entidad
    query = request.GET.get('q')
    if query:
        contactos_list = contactos_list.filter(
            Q(nombres__icontains=query) | 
            Q(apellidos__icontains=query) | 
            Q(correo_electronico__icontains=query) |
            Q(entidad_externa__nombre__icontains=query) # Buscar por nombre de entidad
        )
    
    paginator = Paginator(contactos_list, 25) # 25 contactos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'contactos': page_obj,
        'titulo_pagina': 'Gestionar Contactos Externos',
        'search_query': query or "" # Pasar query a la plantilla para mostrarlo en el input
    }
    return render(request, 'correspondencia/lista_contactos.html', context)

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def crear_contacto(request):
    """Crea un nuevo Contacto Externo (ahora requiere seleccionar EntidadExterna)."""
    if request.method == 'POST':
        # Usar ContactoForm actualizado
        form = ContactoForm(request.POST)
        if form.is_valid():
            try:
                contacto = form.save()
                messages.success(request, f"Contacto '{contacto.nombre_completo}' de la entidad '{contacto.entidad_externa.nombre}' creado exitosamente.")
                return redirect('correspondencia:listar_contactos') # Redirigir a la lista
            except Exception as e:
                 messages.error(request, f"Error al crear el contacto: {e}")
        else:
             messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        # GET: mostrar formulario vacío
        form = ContactoForm()
    
    context = {
        'form': form,
        'titulo_pagina': 'Crear Nuevo Contacto Externo'
    }
    # Reutilizar plantilla de formulario genérica o crear una específica
    return render(request, 'correspondencia/contacto_form.html', context)

# Aquí podríamos añadir vistas para editar_contacto y eliminar_contacto en el futuro.

# === FIN CRUD Contactos ===

# === VISTAS PARA VENTANILLA - RADICACIÓN MANUAL DE CORREOS ===

@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def procesar_emails_manual(request):
    """Vista para ejecutar manualmente el comando procesar_emails."""
    try:
        call_command('procesar_emails')
        messages.success(request, 'Procesamiento de correos iniciado exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al procesar correos: {str(e)}')
    
    # Redirigir a la página anterior o a la bandeja de correos pendientes
    return redirect(request.META.get('HTTP_REFERER', 'correspondencia:bandeja_correos_pendientes'))

# === VISTAS PARA RESPUESTA DE CORRESPONDENCIA (USUARIO REGULAR) ===

@login_required
def crear_o_editar_respuesta(request, correspondencia_entrada_id):
    """Crea una nueva respuesta o edita una existente en estado Borrador o Rechazada."""
    correspondencia_entrada = get_object_or_404(Correspondencia, pk=correspondencia_entrada_id)
    respuesta_existente = CorrespondenciaSalida.objects.filter(respuesta_a=correspondencia_entrada).first()
    
    # Verificar permisos: ¿Puede responder a esta correspondencia?
    # Lógica similar a 'puede_compartir' en detalle_correspondencia: asignado inicial o compartido
    perfil_usuario = getattr(request.user, 'perfil', None)
    es_de_oficina_destino = perfil_usuario and perfil_usuario.oficina == correspondencia_entrada.oficina_destino
    es_asignado_inicial = correspondencia_entrada.usuario_destino_inicial == request.user
    fue_compartido_con_usuario = DistribucionInternaUsuario.objects.filter(correspondencia=correspondencia_entrada, usuario_asignado=request.user).exists()
    
    puede_responder = es_de_oficina_destino and (es_asignado_inicial or fue_compartido_con_usuario)
    
    if not correspondencia_entrada.requiere_respuesta:
         messages.error(request, "Esta correspondencia no requiere respuesta.")
         return redirect('correspondencia:detalle_correspondencia', pk=correspondencia_entrada_id)
         
    if not puede_responder:
        messages.error(request, "No tienes permiso para responder a esta correspondencia.")
        return redirect('correspondencia:detalle_correspondencia', pk=correspondencia_entrada_id)
        
    # Determinar si se está creando o editando y si el estado permite edición
    if respuesta_existente:
        if respuesta_existente.estado not in ['BORRADOR', 'RECHAZADA']:
            messages.warning(request, f"La respuesta ya está en estado '{respuesta_existente.get_estado_display()}' y no se puede editar.")
            # Redirigir a la vista de detalle de la *respuesta* si existe, o a la entrada
            # return redirect('correspondencia:detalle_respuesta', pk=respuesta_existente.pk) # Crear esta vista luego
            return redirect('correspondencia:detalle_correspondencia', pk=correspondencia_entrada_id)
        instance = respuesta_existente
        titulo_pagina = f"Editando Respuesta a {correspondencia_entrada.numero_radicado}"
    else:
        instance = None
        titulo_pagina = f"Creando Respuesta a {correspondencia_entrada.numero_radicado}"

    if request.method == 'POST':
        form = RespuestaCorrespondenciaForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            try:
                with transaction.atomic():
                    respuesta = form.save(commit=False)
                    if not instance: # Si es nueva
                        respuesta.respuesta_a = correspondencia_entrada
                        respuesta.usuario_redactor = request.user
                        # Asignar explícitamente el destinatario basado en el remitente original
                        respuesta.destinatario_contacto = correspondencia_entrada.remitente
                        # El estado por defecto es BORRADOR (definido en el modelo)
                        respuesta.estado = 'BORRADOR'
                    respuesta.save()

                    # Guardar adjuntos múltiples
                    adjuntos = request.FILES.getlist('adjuntos_respuesta')
                    for f in adjuntos:
                        AdjuntoSalida.objects.create(
                            correspondencia_salida=respuesta,
                            archivo=f,
                            nombre_original=f.name
                        )
                    
                    # Registrar historial
                    evento_historial = 'CREACION' if not instance else 'MODIFICACION'
                    HistorialSalida.objects.create(
                        correspondencia_salida=respuesta,
                        tipo_evento=evento_historial,
                        usuario=request.user,
                        descripcion="Borrador guardado."
                    )
                    
                    # Determinar a dónde ir según el botón presionado
                    if 'enviar_aprobacion' in request.POST:
                        # Cambiar estado y redirigir a aprobación (o a la vista de envío)
                        respuesta.estado = 'PENDIENTE_APROBACION'
                        respuesta.save(update_fields=['estado'])
                        HistorialSalida.objects.create(
                            correspondencia_salida=respuesta, tipo_evento='ENVIO_APROBACION', usuario=request.user
                        )
                        messages.success(request, f"Respuesta enviada a aprobación.")
                        return redirect('correspondencia:detalle_correspondencia', pk=correspondencia_entrada_id)
                    else: # Guardar borrador
                        messages.success(request, f"Borrador de respuesta guardado exitosamente.")
                        # Permanecer en la misma página para seguir editando
                        return redirect('correspondencia:crear_respuesta', correspondencia_entrada_id=correspondencia_entrada_id)
                        
            except Exception as e:
                messages.error(request, f"Error al guardar la respuesta: {e}")
        else:
             messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = RespuestaCorrespondenciaForm(instance=instance)

    context = {
        'form': form,
        'correspondencia_entrada': correspondencia_entrada,
        'respuesta_existente': respuesta_existente,
        'titulo_pagina': titulo_pagina,
        'adjuntos_actuales': instance.adjuntos.all() if instance else None
    }
    return render(request, 'correspondencia/respuesta_form.html', context)

# --- VISTAS PARA APROBACIÓN DE RESPUESTAS (VENTANILLA) ---

@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def bandeja_respuestas_pendientes(request):
    """Muestra todas las respuestas de salida, no solo las pendientes."""
    respuestas = CorrespondenciaSalida.objects.select_related(
        'respuesta_a', 'usuario_redactor', 'destinatario_contacto'
    ).order_by('-fecha_creacion')
    
    context = {
        'respuestas': respuestas,
        'titulo_pagina': 'Respuestas de Correspondencia Saliente'
    }
    return render(request, 'correspondencia/bandeja_respuestas.html', context)
@login_required
@user_passes_test(lambda u: u.groups.filter(name='Ventanilla').exists(), login_url='correspondencia:welcome')
def revisar_respuesta(request, respuesta_id):
    respuesta = get_object_or_404(
        CorrespondenciaSalida.objects.select_related(
            'respuesta_a__remitente',
            'respuesta_a__oficina_destino',
            'usuario_redactor__perfil',
            'destinatario_contacto'
        ).prefetch_related('adjuntos', 'historial__usuario'),
        pk=respuesta_id
    )

    if respuesta.estado != 'PENDIENTE_APROBACION':
        messages.warning(request, f"Esta respuesta ya no está pendiente de aprobación (Estado: {respuesta.get_estado_display()}).")
        return redirect('correspondencia:bandeja_respuestas_pendientes')

    # Ajustar si es rechazo
    if request.method == 'POST' and 'rechazar' in request.POST:
        form_rechazo = AprobarRechazarRespuestaForm(request.POST)
    else:
        form_rechazo = AprobarRechazarRespuestaForm()
        form_rechazo.fields['motivo_rechazo'].required = False

    if request.method == 'POST':
        if 'aprobar_enviar' in request.POST:
            try:
                usuario_redactor = respuesta.usuario_redactor
                perfil = getattr(usuario_redactor, 'perfil', None)
                contexto = {
                    'nombre_oficina': perfil.oficina.nombre if perfil and perfil.oficina else 'Oficina no especificada',
                    'nombre_funcionario': usuario_redactor.get_full_name() or usuario_redactor.username,
                    'cargo_funcionario': perfil.cargo if perfil and perfil.cargo else 'Cargo no especificado',
                    'cuerpo_respuesta': respuesta.cuerpo,
                }

                html_message = render_to_string('correspondencia/email/respuesta_salida_base.html', contexto)
                plain_message = strip_tags(html_message)
                destinatario_email = respuesta.respuesta_a.remitente.correo_electronico

                if not destinatario_email:
                    raise ValueError("El contacto remitente no tiene correo registrado.")

                adjuntos_email = []
                for adj in respuesta.adjuntos.all():
                    if adj.archivo:
                        try:
                            adj.archivo.open('rb')
                            adjuntos_email.append((
                                adj.nombre_original or os.path.basename(adj.archivo.name),
                                adj.archivo.read(),
                                adj.tipo_mime or 'application/octet-stream'
                              ))
                         finally:
                            adj.archivo.close()
                
                with transaction.atomic():
                    respuesta.estado = 'APROBADA'
                    respuesta.usuario_aprobador = request.user
                    respuesta.fecha_aprobacion = timezone.now()
                    respuesta.destinatario_email = destinatario_email
                    respuesta.save(update_fields=['estado', 'usuario_aprobador', 'fecha_aprobacion', 'destinatario_email'])

                    HistorialSalida.objects.create(
                        correspondencia_salida=respuesta, tipo_evento='APROBACION', usuario=request.user
                    )

                    HistorialSalida.objects.create(
                        correspondencia_salida=respuesta, tipo_evento='INTENTO_ENVIO', usuario=request.user
                    )

                    email = EmailMessage(
                        subject=respuesta.asunto,
                        body=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[destinatario_email]
                    )
                    email.content_subtype = "html"
                    email.body = html_message

                    for nombre, contenido, tipo_mime in adjuntos_email:
                        email.attach(nombre, contenido, tipo_mime)

                    email.send(fail_silently=False)

                    respuesta.estado = 'ENVIADA'
                    respuesta.fecha_envio = timezone.now()
                    respuesta.save(update_fields=['estado', 'fecha_envio'])

                    respuesta.respuesta_a.estado = 'RESPONDIDA'
                    respuesta.respuesta_a.save(update_fields=['estado'])

                    HistorialSalida.objects.create(
                        correspondencia_salida=respuesta, tipo_evento='ENVIO_EXITOSO', usuario=request.user
                    )
                    
                    messages.success(request, f"Respuesta enviada exitosamente a {destinatario_email}.")
                    return redirect('correspondencia:bandeja_respuestas_pendientes')

            except Exception as e:
                respuesta.estado = 'ERROR_ENVIO'
                respuesta.save(update_fields=['estado'])
                HistorialSalida.objects.create(
                    correspondencia_salida=respuesta,
                    tipo_evento='ENVIO_FALLIDO',
                    usuario=request.user,
                    descripcion=f"Error: {e}\n{traceback.format_exc()}"
                )
                messages.error(request, f"Error al enviar la respuesta: {e}")
                return redirect('correspondencia:revisar_respuesta', respuesta_id=respuesta.id)

        elif 'rechazar' in request.POST:
            if form_rechazo.is_valid():
                try:
                    with transaction.atomic():
                        respuesta.estado = 'RECHAZADA'
                        respuesta.usuario_aprobador = request.user
                        respuesta.fecha_aprobacion = timezone.now()
                        respuesta.motivo_rechazo = form_rechazo.cleaned_data['motivo_rechazo']
                        respuesta.save(update_fields=['estado', 'usuario_aprobador', 'fecha_aprobacion', 'motivo_rechazo'])
                        
                        HistorialSalida.objects.create(
                            correspondencia_salida=respuesta,
                            tipo_evento='RECHAZO',
                            usuario=request.user,
                            descripcion=respuesta.motivo_rechazo
                        )
                    messages.warning(request, f"Respuesta {respuesta.numero_radicado_salida} rechazada.")
                    return redirect('correspondencia:bandeja_respuestas_pendientes')
                except Exception as e:
                    messages.error(request, f"Error al rechazar la respuesta: {e}")
            else:
                messages.error(request, "Debe indicar un motivo para el rechazo.")

    return render(request, 'correspondencia/revisar_respuesta.html', {
        'respuesta': respuesta,
        'correspondencia_original': respuesta.respuesta_a,
        'adjuntos_respuesta': respuesta.adjuntos.all(),
        'historial_respuesta': respuesta.historial.all(),
        'form_rechazo': form_rechazo,
        'titulo_pagina': f"Revisar Respuesta {respuesta.numero_radicado_salida}"
    })
# --- FIN VISTAS RESPUESTA --- 

# --- Vista para Historial Consolidado (MEJORADA) --- 
class HistorialCorrespondenciaView(LoginRequiredMixin, View):
    template_name = 'correspondencia/historial_correspondencia.html'
    paginate_by = 25 # Elementos por página

    def get(self, request, *args, **kwargs):
        # Inicializar formulario con datos GET si existen
        form = HistorialFilterForm(request.GET)
        
        # Valores de filtro (inicialmente None)
        oficina_seleccionada = None
        search_term = None
        tipo_seleccionado = None
        estado_entrada_seleccionado = None
        estado_salida_seleccionado = None
        fecha_inicio = None
        fecha_fin = None
        usuario_seleccionado = None

        # Validar y obtener valores del formulario
        if form.is_valid():
            oficina_seleccionada = form.cleaned_data.get('oficina')
            search_term = form.cleaned_data.get('search_term')
            tipo_seleccionado = form.cleaned_data.get('tipo')
            estado_entrada_seleccionado = form.cleaned_data.get('estado_entrada')
            estado_salida_seleccionado = form.cleaned_data.get('estado_salida')
            fecha_inicio = form.cleaned_data.get('fecha_inicio')
            fecha_fin = form.cleaned_data.get('fecha_fin')
            usuario_seleccionado = form.cleaned_data.get('usuario')

        # --- Querysets Base --- 
        entradas_base_qs = Correspondencia.objects.select_related(
            'oficina_destino',
            'remitente',
            'usuario_radicador' # Necesario para filtrar por usuario
        ).annotate(
            event_date=F('fecha_radicacion') 
        )
        salidas_base_qs = CorrespondenciaSalida.objects.select_related(
            'respuesta_a__oficina_destino',
            'respuesta_a__remitente',
            'destinatario_contacto',
            'usuario_redactor', # Necesario para filtrar por usuario
            'usuario_aprobador' # Necesario para filtrar por usuario
        ).annotate(
            event_date=Coalesce('fecha_envio', 'fecha_aprobacion', 'fecha_creacion')
        )

        # --- Aplicar Filtros a Querysets (los que se pueden aplicar antes de combinar) ---
        
        # Filtro: Oficina
        if oficina_seleccionada:
            entradas_base_qs = entradas_base_qs.filter(oficina_destino=oficina_seleccionada)
            salidas_base_qs = salidas_base_qs.filter(respuesta_a__oficina_destino=oficina_seleccionada)

        # Filtro: Rango de Fechas
        if fecha_inicio:
            entradas_base_qs = entradas_base_qs.filter(event_date__gte=fecha_inicio)
            salidas_base_qs = salidas_base_qs.filter(event_date__gte=fecha_inicio)
        if fecha_fin:
            # Ajustar fecha_fin para incluir todo el día
            from datetime import timedelta
            fecha_fin_adjusted = fecha_fin + timedelta(days=1)
            entradas_base_qs = entradas_base_qs.filter(event_date__lt=fecha_fin_adjusted)
            salidas_base_qs = salidas_base_qs.filter(event_date__lt=fecha_fin_adjusted)
        
        # Filtro: Término de Búsqueda (Asunto, Radicado)
        if search_term:
            q_entradas = (
                Q(asunto__icontains=search_term) | 
                Q(numero_radicado__icontains=search_term) | 
                Q(remitente__nombres__icontains=search_term) | # Buscar en nombre remitente
                Q(remitente__apellidos__icontains=search_term) | # Buscar en apellido remitente
                Q(remitente__entidad_externa__nombre__icontains=search_term) # Buscar en entidad remitente
            )
            entradas_base_qs = entradas_base_qs.filter(q_entradas)

            q_salidas = (
                Q(asunto__icontains=search_term) | 
                Q(numero_radicado_salida__icontains=search_term) |
                Q(destinatario_contacto__nombres__icontains=search_term) | # Buscar en nombre destinatario
                Q(destinatario_contacto__apellidos__icontains=search_term) | # Buscar en apellido destinatario
                Q(destinatario_contacto__entidad_externa__nombre__icontains=search_term) # Buscar en entidad destinatario
            )
            salidas_base_qs = salidas_base_qs.filter(q_salidas)

        # --- Preparar Datos para Combinar --- 
        historial_combinado = []

        # Procesar Entradas (si no se filtró solo Salida)
        if tipo_seleccionado != 'Salida':
            entradas_data = [
                {
                    'id': e.id,
                    'tipo': 'Entrada',
                    'fecha': e.event_date,
                    'radicado': e.numero_radicado,
                    'asunto': e.asunto,
                    'oficina': e.oficina_destino.nombre if e.oficina_destino else 'N/A',
                    'estado_display': e.get_estado_display(),
                    'estado_key': e.estado, 
                    'detail_url': reverse_lazy('correspondencia:detalle_correspondencia', kwargs={'pk': e.pk}),
                    'usuario_radicador': e.usuario_radicador, # Guardar para filtrar luego
                    'usuario_redactor': None,
                    'usuario_aprobador': None,
                }
                for e in entradas_base_qs
            ]
            historial_combinado.extend(entradas_data)

        # Procesar Salidas (si no se filtró solo Entrada)
        if tipo_seleccionado != 'Entrada':
            salidas_data = [
                {
                    'id': s.id,
                    'tipo': 'Salida',
                    'fecha': s.event_date,
                    'radicado': s.numero_radicado_salida,
                    'asunto': s.asunto,
                    'oficina': s.respuesta_a.oficina_destino.nombre if s.respuesta_a and s.respuesta_a.oficina_destino else 'N/A',
                    'estado_display': s.get_estado_display(),
                    'estado_key': s.estado,
                    'detail_url': reverse_lazy('correspondencia:revisar_respuesta', kwargs={'respuesta_id': s.pk}) if s.estado in ['PENDIENTE_APROBACION', 'ERROR_ENVIO', 'RECHAZADA'] else '#',
                    'usuario_radicador': None,
                    'usuario_redactor': s.usuario_redactor, # Guardar para filtrar luego
                    'usuario_aprobador': s.usuario_aprobador, # Guardar para filtrar luego
                }
                for s in salidas_base_qs
            ]
            historial_combinado.extend(salidas_data)

        # --- Aplicar Filtros Post-Combinación --- 

        # Filtro: Estado (aplicar a la lista combinada)
        if estado_entrada_seleccionado:
             historial_combinado = [item for item in historial_combinado if item['tipo'] == 'Entrada' and item['estado_key'] == estado_entrada_seleccionado]
        if estado_salida_seleccionado:
             historial_combinado = [item for item in historial_combinado if item['tipo'] == 'Salida' and item['estado_key'] == estado_salida_seleccionado]
             
        # Filtro: Usuario Involucrado (aplicar a la lista combinada)
        if usuario_seleccionado:
            historial_combinado = [item for item in historial_combinado if 
                                   (item['tipo'] == 'Entrada' and item['usuario_radicador'] == usuario_seleccionado) or
                                   (item['tipo'] == 'Salida' and (item['usuario_redactor'] == usuario_seleccionado or item['usuario_aprobador'] == usuario_seleccionado))
                                  ]

        # --- Ordenar Lista Combinada --- 
        historial_combinado = sorted(
            historial_combinado,
            key=lambda x: x['fecha'],
            reverse=True # Más reciente primero
        )

        # --- Paginar Lista Final --- 
        paginator = Paginator(historial_combinado, self.paginate_by)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        # --- Contexto Final --- 
        context = {
            'titulo_pagina': 'Historial de Correspondencia',
            'form': form, # Pasar el formulario (con datos GET si los hay)
            'page_obj': page_obj,
            # Pasar filtros activos a la plantilla para mostrarlos (con label y valor)
            # 'filtros_activos': { # Estructura anterior - Incorrecta para el template
            #     'oficina': oficina_seleccionada,
            #     'search_term': search_term,
            #     'tipo': tipo_seleccionado,
            #     'estado_entrada': estado_entrada_seleccionado,
            #     'estado_salida': estado_salida_seleccionado,
            #     'fecha_inicio': fecha_inicio,
            #     'fecha_fin': fecha_fin,
            #     'usuario': usuario_seleccionado,
            # }
            'filtros_activos': {}
        }

        # Poblar filtros_activos con label y valor solo si el filtro tiene valor
        if form.is_valid(): # Asegurarse que el form es válido para acceder a fields
            for key, value in form.cleaned_data.items():
                if value: # Solo incluir filtros que tienen un valor activo
                    field_label = form.fields[key].label
                    # Para campos ModelChoiceField, obtener la representación string del objeto
                    display_value = value
                    if isinstance(value, models.Model):
                         display_value = str(value)
                    # Para campos ChoiceField, obtener el display
                    elif key in form.fields and hasattr(form.fields[key], 'choices'):
                         # Buscar el display en las choices
                         display_value = dict(form.fields[key].choices).get(value, value)
                         
                    context['filtros_activos'][key] = {
                        'label': field_label,
                        'value': display_value # Usar el valor formateado/display
                    }
                    # Guardar también el valor original por si acaso
                    # context['filtros_activos'][key]['raw_value'] = value 

        return render(request, self.template_name, context)

