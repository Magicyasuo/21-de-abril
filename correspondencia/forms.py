from django import forms
from .models import Correspondencia, SerieDocumental, SubserieDocumental, OficinaProductora, MEDIO_RECEPCION_CHOICES, TIEMPO_RESPUESTA_CHOICES, Contacto, EntidadExterna, CorrespondenciaSalida, AdjuntoSalida, ESTADOS_CORRESPONDENCIA, ESTADOS_SALIDA
from documentos.models import SerieDocumental, SubserieDocumental, OficinaProductora # Importar desde documentos
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML, Div
from crispy_forms.bootstrap import AppendedText, PrependedText

class CorrespondenciaForm(forms.ModelForm):
    """Formulario para radicar nueva correspondencia entrante."""

    # Personalizar widgets para que usen clases de Bootstrap
    remitente = forms.ModelChoiceField(
        queryset=Contacto.objects.all().order_by('entidad_externa__nombre', 'apellidos', 'nombres'), # CORREGIDO: Ordenar por nombre de entidad externa
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True, # Hacerlo requerido para asegurar que se seleccione uno
        label="Remitente (Contacto Externo)",
        empty_label="Seleccione un contacto..." # Texto para la opción vacía
    )
    asunto = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Asunto detallado'})
    )
    serie = forms.ModelChoiceField(
        queryset=SerieDocumental.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False # Permitir no seleccionar serie/subserie inicialmente?
    )
    subserie = forms.ModelChoiceField(
        queryset=SubserieDocumental.objects.none(), # Se carga dinámicamente
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )
    medio_recepcion = forms.ChoiceField(
        choices=MEDIO_RECEPCION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    requiere_respuesta = forms.BooleanField(
        required=False, # No es obligatorio marcarlo
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    tiempo_respuesta = forms.ChoiceField(
        choices=[('', '--------- ')] + list(TIEMPO_RESPUESTA_CHOICES),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False # Solo será requerido si requiere_respuesta es True (se valida en clean)
    )
    oficina_destino = forms.ModelChoiceField(
        queryset=OficinaProductora.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Oficina Destino Inicial"
    )

    class Meta:
        model = Correspondencia
        # Campos que se mostrarán en el formulario
        fields = [
            'remitente',
            'asunto', 
            'serie', 
            'subserie', 
            'medio_recepcion',
            'requiere_respuesta', 
            'tiempo_respuesta',
            'oficina_destino',
            # Añadir campo para adjunto si se implementa en el modelo
            # 'archivo_adjunto',
        ]
        # Widgets adicionales si no se personalizan arriba
        widgets = {
            'asunto': forms.Textarea(attrs={'rows': 3}),
            # Puedes personalizar otros widgets aquí si es necesario
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column(Field('remitente'), css_class='form-group col-md-6 mb-3'),
                Column(Field('medio_recepcion'), css_class='form-group col-md-6 mb-3')
            ),
            Field('asunto', css_class='mb-3'),
            Row(
                Column(Field('oficina_destino'), css_class='form-group col-md-4 mb-3'),
                Column(Field('serie'), css_class='form-group col-md-4 mb-3'),
                Column(Field('subserie'), css_class='form-group col-md-4 mb-3'),
            ),
            Row(
                Column(Field('requiere_respuesta', css_class='form-check-input'), css_class='form-group col-md-6 mb-3'),
                Column(Field('tiempo_respuesta'), css_class='form-group col-md-6 mb-3', id='div_tiempo_respuesta'),
            ),
            # Botón de envío estándar de Crispy Forms
            Submit('submit', 'Radicar Correspondencia', css_class='btn btn-primary mt-3')
        )
        # Lógica para cargar subseries dinámicamente basada en la serie seleccionada
        if 'serie' in self.data:
            try:
                serie_id = int(self.data.get('serie'))
                self.fields['subserie'].queryset = SubserieDocumental.objects.filter(serie_id=serie_id).order_by('nombre')
            except (ValueError, TypeError):
                self.fields['subserie'].queryset = SubserieDocumental.objects.none()
        elif self.instance.pk and self.instance.serie:
            self.fields['subserie'].queryset = SubserieDocumental.objects.filter(serie=self.instance.serie).order_by('nombre')
        else:
            self.fields['subserie'].queryset = SubserieDocumental.objects.none()
            
        # Opcional: Ordenar queryset de OficinaProductora
        self.fields['oficina_destino'].queryset = OficinaProductora.objects.order_by('nombre')

        # Configurar Select2 para otros campos si es necesario
        if 'oficina_destino' in self.fields:
            self.fields['oficina_destino'].widget.attrs.update({'class': 'form-select select2'})
        if 'serie' in self.fields:
            self.fields['serie'].widget.attrs.update({'class': 'form-select select2'})
        if 'subserie' in self.fields:
            self.fields['subserie'].widget.attrs.update({'class': 'form-select select2'})
        if 'medio_recepcion' in self.fields:
            self.fields['medio_recepcion'].widget.attrs.update({'class': 'form-select'})
        if 'tiempo_respuesta' in self.fields:
             self.fields['tiempo_respuesta'].widget.attrs.update({'class': 'form-select'})

    def clean(self):
        cleaned_data = super().clean()
        requiere_respuesta = cleaned_data.get("requiere_respuesta")
        tiempo_respuesta = cleaned_data.get("tiempo_respuesta")

        if requiere_respuesta and not tiempo_respuesta:
            # Si marca que requiere respuesta, el tiempo es obligatorio
            self.add_error('tiempo_respuesta', "Debe seleccionar un tiempo de respuesta si la correspondencia lo requiere.")
        elif not requiere_respuesta:
            # Si no requiere respuesta, nos aseguramos que el tiempo quede vacío
            cleaned_data['tiempo_respuesta'] = None

        return cleaned_data 

class ContactoForm(forms.ModelForm):
    """Formulario para crear o editar Contactos Externos."""

    class Meta:
        model = Contacto
        # Actualizar fields: quitar 'entidad', añadir 'entidad_externa' y los nuevos campos
        fields = [
            'entidad_externa',
            'nombres', 
            'apellidos', 
            'cargo', 
            'correo_electronico',
            'telefono_contacto'
        ]
        widgets = {
            # Usar Select para la ForeignKey entidad_externa
            'entidad_externa': forms.Select(attrs={'class': 'form-select select2'}),
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cargo (Opcional)'}),
            'correo_electronico': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ejemplo@dominio.com'}),
            'telefono_contacto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono (Opcional)'}),
        }
        labels = {
            'entidad_externa': 'Entidad Externa',
            'telefono_contacto': 'Teléfono del Contacto',
        }
        help_texts = {
             'entidad_externa': 'Seleccione la entidad a la que pertenece este contacto.'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False 
        self.helper.disable_csrf = False
        self.helper.layout = Layout(
            # Actualizar layout con los nuevos campos
            Field('entidad_externa', css_class="mb-3"),
            Row(
                Column(Field('nombres'), css_class='form-group col-md-6 mb-3'),
                Column(Field('apellidos'), css_class='form-group col-md-6 mb-3')
            ),
             Row(
                Column(Field('cargo'), css_class='form-group col-md-6 mb-3'),
                Column(Field('correo_electronico'), css_class='form-group col-md-6 mb-3')
            ),
            Field('telefono_contacto', css_class="mb-3"),
        )
        # Asegurar que el queryset para entidad_externa esté ordenado
        self.fields['entidad_externa'].queryset = EntidadExterna.objects.order_by('nombre')

class CompartirCorrespondenciaForm(forms.Form):
    """Formulario para compartir correspondencia con usuarios de la misma oficina."""
    usuarios = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(), # Queryset inicial vacío, se llenará en __init__
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Seleccionar usuarios para compartir"
    )
    observaciones = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label="Observaciones (opcional)"
    )

    def __init__(self, *args, **kwargs):
        # Obtener la oficina y el usuario actual pasados desde la vista
        oficina = kwargs.pop('oficina', None)
        usuario_actual = kwargs.pop('usuario_actual', None)
        super().__init__(*args, **kwargs)

        if oficina and usuario_actual:
            # Filtrar usuarios de la misma oficina, excluyendo al usuario actual
            self.fields['usuarios'].queryset = User.objects.filter(
                perfil__oficina=oficina
            ).exclude(
                pk=usuario_actual.pk
            ).select_related('perfil') # Optimizar
            
            # Personalizar label si se quiere
            # self.fields['usuarios'].label = f"Compartir con colegas de {oficina.nombre}"

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('usuarios', css_class='mb-3'),
            Field('observaciones', css_class='mb-3'),
            Submit('submit', 'Compartir', css_class='btn btn-info')
        )

# --- Nuevo Formulario para Radicación Manual desde Correo ---
class ManualRadicacionCorreoForm(forms.ModelForm):
    """Formulario específico para la radicación manual desde la vista de detalle del correo."""

    class Meta:
        model = Correspondencia
        # Campos estrictamente necesarios para la radicación manual desde correo
        fields = [
            'remitente',
            'asunto',
            'oficina_destino',
            'serie',
            'subserie',
            'requiere_respuesta',
            'tiempo_respuesta',
        ]
        widgets = {
            'remitente': forms.Select(attrs={'class': 'form-select select2'}),
            'asunto': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'oficina_destino': forms.Select(attrs={'class': 'form-select select2'}),
            'serie': forms.Select(attrs={'class': 'form-select select2'}),
            'subserie': forms.Select(attrs={'class': 'form-select select2'}), # Inicialmente vacío/deshabilitado
            'tiempo_respuesta': forms.Select(attrs={'class': 'form-select'}), # Se mostrará/ocultará con JS
            'requiere_respuesta': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'remitente': 'Remitente (Contacto Registrado)',
            'oficina_destino': 'Oficina Destino Inicial',
            'serie': 'Serie Documental',
            'subserie': 'Subserie Documental',
            'requiere_respuesta': '¿Requiere Respuesta?',
            'tiempo_respuesta': 'Plazo de Respuesta',
        }
        help_texts = {
            'remitente': 'Busque un contacto existente. Si no existe, debe crearlo usando el botón "Crear Contacto".',
            'subserie': 'Se carga automáticamente al seleccionar una serie.'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ordenar Querysets para los Selects
        self.fields['remitente'].queryset = Contacto.objects.select_related('entidad_externa').order_by('entidad_externa__nombre', 'apellidos', 'nombres')
        self.fields['oficina_destino'].queryset = OficinaProductora.objects.order_by('nombre')
        self.fields['serie'].queryset = SerieDocumental.objects.order_by('nombre')

        # Configurar Subserie: inicialmente vacío o basado en la instancia/datos
        serie_actual = None
        if 'serie' in self.data:
            try:
                serie_id = int(self.data.get('serie'))
                serie_actual = SerieDocumental.objects.get(pk=serie_id)
            except (ValueError, TypeError, SerieDocumental.DoesNotExist):
                pass
        elif self.instance.pk and self.instance.serie:
            serie_actual = self.instance.serie

        if serie_actual:
            self.fields['subserie'].queryset = SubserieDocumental.objects.filter(serie=serie_actual).order_by('nombre')
          #  self.fields['subserie'].disabled = False # Descomentar si se quiere habilitar siempre
        else:
            # Si no hay serie seleccionada, mostrar todas las subseries ordenadas por serie y nombre.
            # Opcional: Podrías dejarlo vacío (objects.none()) y deshabilitarlo
            self.fields['subserie'].queryset = SubserieDocumental.objects.order_by('serie__nombre', 'nombre')
            self.fields['subserie'].disabled = False # Mantener habilitado para seleccionar si se desea

        # Crispy Forms Helper para el layout dentro del modal
        self.helper = FormHelper()
        self.helper.form_tag = False # Importante: El <form> estará en el HTML del modal
        self.helper.disable_csrf = True # CSRF token estará en el <form> del modal
        self.helper.layout = Layout(
            # No añadir un título H5 aquí, estará en el modal header
            Field('remitente', css_class="mb-3"),
            Field('asunto', css_class="mb-3"),
            Row(
                Column(Field('oficina_destino'), css_class='col-md-12 mb-3'),
            ),
            Row(
                Column(Field('serie'), css_class='col-md-6 mb-3'),
                Column(Field('subserie'), css_class='col-md-6 mb-3'),
            ),
            Row(
                 # Usar la estructura de Bootstrap para switches
                Column(
                    HTML('<div class="form-check form-switch mb-3">'),
                    Field('requiere_respuesta', css_class='form-check-input', id='id_radicar-requiere_respuesta'), # Asegurar ID único con prefijo
                    HTML('<label class="form-check-label" for="id_radicar-requiere_respuesta">¿Requiere Respuesta?</label>'),
                    HTML('</div>'),
                    css_class='col-md-6'
                ),
                Column(Field('tiempo_respuesta'), css_class='col-md-6 mb-3', id='div_id_radicar-tiempo_respuesta'), # ID único con prefijo
            ),
            # No incluir botón Submit aquí, estará en el modal footer
        )

    def clean(self):
        cleaned_data = super().clean()
        requiere_respuesta = cleaned_data.get('requiere_respuesta')
        tiempo_respuesta = cleaned_data.get('tiempo_respuesta')

        # Validación: Si requiere respuesta, el tiempo es obligatorio
        if requiere_respuesta and not tiempo_respuesta:
            self.add_error('tiempo_respuesta', 'Debe seleccionar un tiempo de respuesta.')

        # Limpieza: Si no requiere respuesta, asegurar que tiempo_respuesta sea None
        if not requiere_respuesta:
            cleaned_data['tiempo_respuesta'] = None

        return cleaned_data

# --- Formulario para Entidad Externa (NUEVO) ---
class EntidadExternaForm(forms.ModelForm):
    """Formulario para crear y editar Entidades Externas."""
    class Meta:
        model = EntidadExterna
        fields = ['nombre', 'nit', 'direccion', 'telefono']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre completo de la entidad'}),
            'nit': forms.TextInput(attrs={'placeholder': 'NIT o identificador (opcional)'}),
            'direccion': forms.TextInput(attrs={'placeholder': 'Dirección (opcional)'}),
            'telefono': forms.TextInput(attrs={'placeholder': 'Teléfono principal (opcional)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        # Asumiendo que este form SÍ necesita su propio tag <form>
        self.helper.layout = Layout(
            Field('nombre', css_class="mb-3"),
            Row(
                Column(Field('nit'), css_class='form-group col-md-6 mb-3'),
                Column(Field('telefono'), css_class='form-group col-md-6 mb-3')
            ),
            Field('direccion', css_class="mb-3"),
            Submit('submit', 'Guardar Entidad', css_class='btn btn-primary mt-3')
        )

# ==============================================
# === FORMULARIOS PARA CORRESPONDENCIA SALIDA ===
# ==============================================
from django import forms
from django.forms.widgets import FileInput
from .models import CorrespondenciaSalida

class RespuestaCorrespondenciaForm(forms.ModelForm):
    class Meta:
        model = CorrespondenciaSalida
        fields = ['asunto', 'cuerpo']
        widgets = {
            'asunto': forms.TextInput(attrs={
                'placeholder': 'Asunto claro y conciso',
                'class': 'form-control'
            }),
            'cuerpo': forms.Textarea(attrs={
                'rows': 10,
                'placeholder': 'Escriba aquí el cuerpo de la respuesta...',
                'class': 'form-control'
            }),
        }

class AprobarRechazarRespuestaForm(forms.Form):
    motivo_rechazo = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=True,
        label="Motivo del Rechazo"
    )

# --- Formulario AVANZADO para Filtro de Historial ---

# Crear listas de opciones para estados combinados
ESTADOS_ENTRADA_CHOICES = [('', '--- Estado Entrada ---')] + [(k, f"Entrada - {v}") for k, v in ESTADOS_CORRESPONDENCIA]
ESTADOS_SALIDA_CHOICES = [('', '--- Estado Salida ---')] + [(k, f"Salida - {v}") for k, v in ESTADOS_SALIDA]
# Combinar todos los estados posibles para un único filtro (opcional, podría ser complejo) 
# ALL_STATUS_CHOICES = [('', '-- Cualquier Estado --')] + ESTADOS_ENTRADA_CHOICES[1:] + ESTADOS_SALIDA_CHOICES[1:]

TIPO_CHOICES = (
    ('', 'Entrada y Salida'),
    ('Entrada', 'Solo Entrada'),
    ('Salida', 'Solo Salida'),
)

class HistorialFilterForm(forms.Form):
    search_term = forms.CharField(
        required=False,
        label="Buscar (Asunto, Radicado...)",
        widget=forms.TextInput(attrs={'placeholder': 'Término de búsqueda...', 'class': 'form-control-sm'})
    )
    oficina = forms.ModelChoiceField(
        queryset=OficinaProductora.objects.all().order_by('nombre'),
        required=False,
        label="Oficina",
        empty_label="-- Todas --",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm select2'})
    )
    tipo = forms.ChoiceField(
        choices=TIPO_CHOICES,
        required=False,
        label="Tipo",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    # Usaremos dos campos de estado separados por simplicidad en el filtrado de la vista
    estado_entrada = forms.ChoiceField(
        choices=ESTADOS_ENTRADA_CHOICES,
        required=False,
        label="Estado Entrada",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    estado_salida = forms.ChoiceField(
        choices=ESTADOS_SALIDA_CHOICES,
        required=False,
        label="Estado Salida",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    # status = forms.ChoiceField( # Opción alternativa: Un solo campo de estado
    #     choices=ALL_STATUS_CHOICES,
    #     required=False,
    #     label="Estado",
    #     widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    # )
    fecha_inicio = forms.DateField(
        required=False,
        label="Desde",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'})
    )
    fecha_fin = forms.DateField(
        required=False,
        label="Hasta",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'})
    )
    usuario = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('username'),
        required=False,
        label="Usuario Involucrado",
        empty_label="-- Todos --",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm select2'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'get' # El filtro se aplica vía GET
        self.helper.form_class = 'form-horizontal' # O form-vertical si prefieres
        self.helper.label_class = 'col-lg-3' # Ajustar según necesidad
        self.helper.field_class = 'col-lg-9' # Ajustar según necesidad
        self.helper.layout = Layout(
            Row(
                Column(Field('search_term'), css_class='col-md-6 mb-2'),
                Column(Field('tipo'), css_class='col-md-3 mb-2'),
                Column(Field('oficina'), css_class='col-md-3 mb-2')
            ),
            Row(
                Column(Field('estado_entrada'), css_class='col-md-3 mb-2'),
                Column(Field('estado_salida'), css_class='col-md-3 mb-2'),
                Column(Field('usuario'), css_class='col-md-6 mb-2')
            ),
            Row(
                 Column(Field('fecha_inicio'), css_class='col-md-3 mb-2'),
                 Column(Field('fecha_fin'), css_class='col-md-3 mb-2'),
                 Column(
                     Submit('submit', 'Aplicar Filtros', css_class='btn btn-primary btn-sm w-100'), # Botón dentro de la última fila
                     css_class='col-md-3 align-self-end mb-2' # Alinear al final
                 ),
                 Column(
                     Submit('reset', 'Limpiar Filtros', css_class='btn btn-secondary btn-sm w-100'), # Usar Submit tipo reset como alternativa
                     css_class='col-md-3 align-self-end mb-2'
                 )
            ),
        )
        # No añadimos botón submit global, está en el layout
        # self.helper.add_input(Submit('submit', 'Filtrar'))