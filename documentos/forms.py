from django import forms
from .models import RegistroDeArchivo, SerieDocumental, SubserieDocumental
from django.utils.timezone import now
from django.forms import DateInput
from django import forms
from .models import FUID, RegistroDeArchivo
from django.utils.timezone import now, timedelta
from django.contrib.auth.models import User  # IMPORTAR User
# from .forms import FichaPacienteForm



from django import forms
from django.utils.timezone import now
from .models import RegistroDeArchivo, SubserieDocumental

from django import forms
from django.utils.timezone import now
from django.core.exceptions import ValidationError

# documentos/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from .models import RegistroDeArchivo, SubserieDocumental
from .models import Documento  # si necesitas usarlo en este archivo
from django.conf import settings

# Tu validador de tamaño
def validate_file_size(value):
    max_size = 10 * 1024 * 1024  # 10 MB
    if value.size > max_size:
        raise ValidationError("El archivo no puede superar los 10 MB.")

class RegistroDeArchivoForm(forms.ModelForm):
    # Aplica el validador al campo archivo
    archivo = forms.FileField(
        required=False,
        help_text="Sube un documento (máx 10 MB).",
        validators=[validate_file_size]
    )

    fecha_archivo = forms.DateField(
        required=False,
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        ),
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
    )

    fecha_inicial = forms.DateField(
        required=False,
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        ),
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
    )

    fecha_final = forms.DateField(
        required=False,
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control'}
        ),
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
    )

    class Meta:
        model = RegistroDeArchivo
        exclude = ['creado_por']
        widgets = {
            'Estado_archivo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Evitar que 'ubicacion' sea requerida
        self.fields['ubicacion'].required = False

        # Asignar fecha_archivo por defecto en el formulario
        if not self.instance.pk:
            self.fields['fecha_archivo'].initial = now().date()

        # Configuración dinámica de subseries
        if 'codigo_serie' in self.data:
            try:
                serie_id = int(self.data.get('codigo_serie'))
                self.fields['codigo_subserie'].queryset = SubserieDocumental.objects.filter(serie_id=serie_id)
            except (ValueError, TypeError):
                self.fields['codigo_subserie'].queryset = SubserieDocumental.objects.none()
        elif self.instance.pk and self.instance.codigo_serie:
            self.fields['codigo_subserie'].queryset = SubserieDocumental.objects.filter(serie_id=self.instance.codigo_serie.id)
        else:
            self.fields['codigo_subserie'].queryset = SubserieDocumental.objects.none()

    def clean(self):
        cleaned_data = super().clean()

        # Si fecha_archivo está vacío, asignar la fecha actual
        if not cleaned_data.get('fecha_archivo'):
            cleaned_data['fecha_archivo'] = now().date()

        # Soporte Físico
        if not cleaned_data.get('soporte_fisico'):
            cleaned_data['caja'] = 0
            cleaned_data['carpeta'] = 0
            cleaned_data['tomo_legajo_libro'] = "N/A"
            cleaned_data['numero_folios'] = 0
            cleaned_data['tipo'] = "N/A"
            cleaned_data['cantidad'] = 0

        # Soporte Electrónico
        if not cleaned_data.get('soporte_electronico'):
            cleaned_data['ubicacion'] = "N/A"
            cleaned_data['cantidad_documentos_electronicos'] = 0
            cleaned_data['tamano_documentos_electronicos'] = "N/A"

        return cleaned_data




class FUIDForm(forms.ModelForm):
    # Campos y configuración del formulario
    usuario = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Filtrar por Usuario",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    fecha_inicio = forms.DateField(
        required=False,
        label="Fecha Inicio",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    fecha_fin = forms.DateField(
        required=False,
        label="Fecha Fin",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    registros = forms.ModelMultipleChoiceField(
        queryset=RegistroDeArchivo.objects.none(),  
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Registros Asociados"
    )

    elaborado_por_nombre = forms.CharField(
        required=False,
        max_length=255,
        label="Elaborado Por (Nombre)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    elaborado_por_cargo = forms.CharField(
        required=False,
        max_length=255,
        label="Elaborado Por (Cargo)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    elaborado_por_lugar = forms.CharField(
        required=False,
        max_length=255,
        label="Elaborado Por (Lugar)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    elaborado_por_fecha = forms.DateField(
        required=False,
        label="Elaborado Por (Fecha)",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    entregado_por_nombre = forms.CharField(
        required=False,
        max_length=255,
        label="Entregado Por (Nombre)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    entregado_por_cargo = forms.CharField(
        required=False,
        max_length=255,
        label="Entregado Por (Cargo)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    entregado_por_lugar = forms.CharField(
        required=False,
        max_length=255,
        label="Entregado Por (Lugar)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    entregado_por_fecha = forms.DateField(
        required=False,
        label="Entregado Por (Fecha)",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    recibido_por_nombre = forms.CharField(
        required=False,
        max_length=255,
        label="Recibido Por (Nombre)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    recibido_por_cargo = forms.CharField(
        required=False,
        max_length=255,
        label="Recibido Por (Cargo)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    recibido_por_lugar = forms.CharField(
        required=False,
        max_length=255,
        label="Recibido Por (Lugar)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    recibido_por_fecha = forms.DateField(
        required=False,
        label="Recibido Por (Fecha)",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = FUID
        fields = [
            'entidad_productora', 'unidad_administrativa', 'oficina_productora', 'objeto',
            'registros',
            'elaborado_por_nombre', 'elaborado_por_cargo', 'elaborado_por_lugar', 'elaborado_por_fecha',
            'entregado_por_nombre', 'entregado_por_cargo', 'entregado_por_lugar', 'entregado_por_fecha',
            'recibido_por_nombre', 'recibido_por_cargo', 'recibido_por_lugar', 'recibido_por_fecha'
        ]
        widgets = {
            'entidad_productora': forms.Select(attrs={'class': 'form-select'}),
            'unidad_administrativa': forms.Select(attrs={'class': 'form-select'}),
            'oficina_productora': forms.Select(attrs={'class': 'form-select'}),
            'objeto': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)  # Usuario autenticado
        # No es necesario asignar self.instance aquí, ModelForm ya lo hace
        super().__init__(*args, **kwargs)

        # Configura el queryset de registros
        if self.instance and self.instance.pk:
            registros_actuales = self.instance.registros.all()
            registros_disponibles = RegistroDeArchivo.objects.filter(fuids__isnull=True)
            self.fields['registros'].queryset = registros_actuales | registros_disponibles
        else:
            self.fields['registros'].queryset = RegistroDeArchivo.objects.filter(fuids__isnull=True)
  

from django import forms
from .models import FichaPaciente

class FichaPacienteForm(forms.ModelForm):
    class Meta:
        model = FichaPaciente
        fields = '__all__'
        widgets = {
            'primer_nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingresa el primer nombre',
                'autofocus': 'autofocus',  # Enfocar este campo automáticamente
            }),
            'segundo_nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingresa el segundo nombre (opcional)',
            }),
            'primer_apellido': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingresa el primer apellido',
            }),
            'segundo_apellido': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingresa el segundo apellido (opcional)',
            }),
            'num_identificacion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de identificación único',
            }),
            'fecha_nacimiento': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',  # Mostrar un selector de fecha
            }),
            'primer_nombre_padre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingresa el primer nombre del padre',
            }),
            'segundo_nombre_padre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Segundo nombre del padre (opcional)',
            }),
            'primer_apellido_padre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingresa el primer apellido del padre',
            }),
            'segundo_apellido_padre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Segundo apellido del padre (opcional)',
            }),
            'Numero_historia_clinica': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de historia clínica único',
            }),
            'caja': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de caja',
            }),
            'carpeta': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de carpeta',

            }),
            'Activo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Estado',
                
            }),                 
        }

    def clean_Numero_historia_clinica(self):
        numero_historia_clinica = self.cleaned_data.get('Numero_historia_clinica')
        if FichaPaciente.objects.filter(Numero_historia_clinica=numero_historia_clinica).exists():
            raise forms.ValidationError("El número de historia clínica ya está registrado. Por favor, verifica los datos.")
        return numero_historia_clinica

    def clean_num_identificacion(self):
        num_identificacion = self.cleaned_data.get('num_identificacion')
        if FichaPaciente.objects.filter(num_identificacion=num_identificacion).exists():
            raise forms.ValidationError("El número de identificación ya está registrado. Por favor, verifica los datos.")
        return num_identificacion
