# import os
# import sys
# import django
# import csv
# from django.db import transaction

# # 📌 Agrega la raíz del proyecto al path de Python (para evitar errores de importación)
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# # 📌 Configurar Django antes de importar modelos
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hospital_document_management.settings")
# django.setup()

# # 📌 Importar modelos después de configurar Django
# from documentos.models import (
#     EntidadProductora,
#     UnidadAdministrativa,
#     OficinaProductora,
#     SerieDocumental,
#     SubserieDocumental
# )

# # 📌 Ruta donde están los archivos CSV exportados
# DATA_PATH = "/home/devsarare/Descargas/maquinaupdates/Privado-maquina-20250219T211538Z-001/Privado-maquina/dataUnidad"

# def leer_csv(nombre_archivo):
#     """Lee un archivo CSV y devuelve su contenido como lista"""
#     ruta_completa = os.path.join(DATA_PATH, nombre_archivo)
    
#     if not os.path.exists(ruta_completa):
#         print(f"❌ ERROR: No se encontró el archivo {nombre_archivo}")
#         return []

#     with open(ruta_completa, newline='', encoding='utf-8') as archivo:
#         return list(csv.reader(archivo, delimiter=","))

# def importar_entidades():
#     """ Importa EntidadProductora desde CSV """
#     print("📌 Importando EntidadProductora...")
#     entidades = {}
#     for row in leer_csv("EntidadProductora.csv"):
#         if not row: continue
#         id_entidad, nombre = row[:2]
#         entidad, _ = EntidadProductora.objects.get_or_create(nombre=nombre.strip())
#         entidades[str(id_entidad)] = entidad
#     print(f"✅ {len(entidades)} Entidades importadas.")
#     return entidades

# def importar_unidades(entidades):
#     """ Importa UnidadAdministrativa y la asocia con EntidadProductora """
#     print("📌 Importando UnidadAdministrativa...")
#     unidades = {}
#     for row in leer_csv("UnidadAdministrativa.csv"):
#         if not row: continue
#         id_unidad, nombre, entidad_id = row[:3]
#         entidad = entidades.get(str(entidad_id))
#         if entidad:
#             unidad, _ = UnidadAdministrativa.objects.get_or_create(
#                 nombre=nombre.strip(),
#                 entidad_productora=entidad
#             )
#             unidades[str(id_unidad)] = unidad
#     print(f"✅ {len(unidades)} Unidades Administrativas importadas.")
#     return unidades

# def importar_oficinas(unidades):
#     """ Importa OficinaProductora y la asocia con UnidadAdministrativa """
#     print("📌 Importando OficinaProductora...")
#     oficinas = {}
#     for row in leer_csv("OficinaProductora.csv"):
#         if not row: continue
#         id_oficina, nombre, unidad_id = row[:3]
#         unidad = unidades.get(str(unidad_id))
#         if unidad:
#             oficina, _ = OficinaProductora.objects.get_or_create(
#                 nombre=nombre.strip(),
#                 unidad_administrativa=unidad
#             )
#             oficinas[str(id_oficina)] = oficina
#     print(f"✅ {len(oficinas)} Oficinas importadas.")
#     return oficinas

# def importar_series():
#     """ Importa SerieDocumental """
#     print("📌 Importando SerieDocumental...")
#     series = {}
#     for row in leer_csv("SerieDocumental.csv"):
#         if not row: continue
#         id_serie, codigo, nombre = row[:3]
#         serie, _ = SerieDocumental.objects.get_or_create(
#             codigo=codigo.strip(),
#             nombre=nombre.strip()
#         )
#         series[str(id_serie)] = serie
#     print(f"✅ {len(series)} Series importadas.")
#     return series

# def importar_subseries(series):
#     """ Importa SubserieDocumental y la asocia con SerieDocumental """
#     print("📌 Importando SubserieDocumental...")
#     subseries_count = 0
#     for row in leer_csv("SubserieDocumental.csv"):
#         if not row: continue
#         id_subserie, codigo, nombre, serie_id = row[:4]
#         serie = series.get(str(serie_id))
#         if serie:
#             SubserieDocumental.objects.get_or_create(
#                 codigo=codigo.strip(),
#                 nombre=nombre.strip(),
#                 serie=serie
#             )
#             subseries_count += 1
#     print(f"✅ {subseries_count} Subseries importadas.")

# def main():
#     """ Función principal para importar todos los datos """
#     try:
#         with transaction.atomic():
#             print("\n🔄 Iniciando Importación de Datos desde CSV...\n")
#             entidades = importar_entidades()
#             unidades = importar_unidades(entidades)
#             oficinas = importar_oficinas(unidades)
#             series = importar_series()
#             importar_subseries(series)

#             print("\n✅ Importación completada correctamente desde los archivos CSV.")

#     except Exception as e:
#         print(f"\n❌ ERROR en la importación: {e}")

# if __name__ == "__main__":
#     main()



# # # # # # # # # # # # # # # # # # creacion de oficinas productoras



import os
import re
import django
import unicodedata
import secrets

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hospital_document_management.settings")
django.setup()

from django.contrib.auth.models import User, Group
from documentos.models import OficinaProductora, PerfilUsuario


def slugify_oficina(nombre_oficina: str) -> str:
    """
    Convierte el nombre de la oficina a un formato 'slug'
    usando puntos en lugar de espacios/caracteres especiales.
    Ej: "Gestión de la Calidad" -> "gestion.de.la.calidad"
    """
    # 1) Quitar acentos
    normalized = unicodedata.normalize('NFD', nombre_oficina)
    sin_acentos = "".join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
    # 2) Pasar a minúsculas
    sin_acentos = sin_acentos.lower()
    # 3) Reemplazar cualquier carácter que no sea alfanumérico por un punto
    slug = re.sub(r'[^a-z0-9]+', '.', sin_acentos)
    # 4) Quitar posibles puntos duplicados, al inicio o final
    slug = slug.strip('.')
    return slug


def run():
    print("=== Creación masiva de usuarios por Oficina ===\n")

    # 1) Obtener o crear grupos "avanzado" y "normal"
    grupo_avanzado, _ = Group.objects.get_or_create(name="avanzado")
    grupo_normal, _ = Group.objects.get_or_create(name="normal")

    # 2) Tomar todas las oficinas
    oficinas = OficinaProductora.objects.all().order_by('id')
    total_usuarios_creados = 0

    # Almacenar la info para imprimirla al final
    info_usuarios = []  # [(username, password, grupo, oficina), ...]

    for oficina in oficinas:
        base_slug = slugify_oficina(oficina.nombre)

        # Crear 4 usuarios por oficina
        for i in range(1, 5):
            username = f"{base_slug}{i}"
            # Generar una contraseña aleatoria (12 caracteres, mezcla de letras y símbolos)
            password = secrets.token_urlsafe(12)

            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    is_superuser=False,
                    is_staff=False
                )
                # Asignar grupo
                if i == 1:
                    user.groups.add(grupo_avanzado)
                    grupo_usuario = "avanzado"
                else:
                    user.groups.add(grupo_normal)
                    grupo_usuario = "normal"

                # ✅ Crear o actualizar perfil asegurando que `oficina` se asigna en la creación
                perfil, _ = PerfilUsuario.objects.get_or_create(
                    user=user,
                    defaults={'oficina': oficina}  # ✅ Se asigna oficina al crearlo
                )

                total_usuarios_creados += 1

                # Guardar la info en memoria para imprimir
                info_usuarios.append((username, password, grupo_usuario, oficina.nombre))

            else:
                # Si el usuario ya existe, lo ignoramos (no creamos nada nuevo)
                info_usuarios.append((username, "(ya existe)", "(sin cambios)", oficina.nombre))

    print(f"Se crearon {total_usuarios_creados} usuarios nuevos.\n")

    print("=== Detalles de todos los usuarios procesados ===")
    print("(Puedes copiar y pegar esta información)")
    print("Username | Password | Grupo | Oficina")
    print("---------------------------------------------------------")

    for username, password, grupo, oficina_str in info_usuarios:
        print(f"{username} | {password} | {grupo} | {oficina_str}")

    print("\n=== Proceso finalizado ===")


if __name__ == "__main__":
    run()
