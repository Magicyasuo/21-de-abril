from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils.timezone import now
from .models import FUID, RegistroDeArchivo, FichaPaciente


def obtener_fuids_por_usuario():
    """
    Devuelve la cantidad total de FUIDs creados por cada usuario.
    """
    return FUID.objects.values('creado_por__username').annotate(total=Count('id')).order_by('-total')


def obtener_registros_mensuales():
    """
    Devuelve la cantidad de registros creados agrupados por mes (último año).
    """
    return (
        RegistroDeArchivo.objects.filter(fecha_creacion__year=now().year)
        .annotate(mes=TruncMonth('fecha_creacion'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )


def obtener_pacientes_por_genero_estado():
    """
    Devuelve la cantidad de pacientes agrupados por género y estado (activo/inactivo).
    """
    return FichaPaciente.objects.values('sexo', 'activo').annotate(total=Count('id'))
