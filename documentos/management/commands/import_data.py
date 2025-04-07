from django.core.management.base import BaseCommand
import os
import re
import django
import unicodedata
import secrets

from django.contrib.auth.models import User, Group
from documentos.models import OficinaProductora, PerfilUsuario

def slugify_oficina(nombre_oficina: str) -> str:
    """
    Convierte el nombre de la oficina a un formato 'slug'.
    Ej: "Gestión de la Calidad" -> "gestion.de.la.calidad"
    """
    normalized = unicodedata.normalize('NFD', nombre_oficina)
    sin_acentos = "".join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
    sin_acentos = sin_acentos.lower()
    slug = re.sub(r'[^a-z0-9]+', '.', sin_acentos).strip('.')
    return slug

class Command(BaseCommand):
    help = "Crea usuarios masivamente por oficina"

    def handle(self, *args, **kwargs):
        print("=== Creación masiva de usuarios por Oficina ===\n")

        grupo_avanzado, _ = Group.objects.get_or_create(name="avanzado")
        grupo_normal, _ = Group.objects.get_or_create(name="normal")

        oficinas = OficinaProductora.objects.all().order_by('id')
        total_usuarios_creados = 0
        info_usuarios = []  # [(username, password, grupo, oficina), ...]

        for oficina in oficinas:
            base_slug = slugify_oficina(oficina.nombre)

            for i in range(1, 5):
                username = f"{base_slug}{i}"
                password = secrets.token_urlsafe(12)

                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(
                        username=username,
                        password=password,
                        is_superuser=False,
                        is_staff=False
                    )
                    if i == 1:
                        user.groups.add(grupo_avanzado)
                        grupo_usuario = "avanzado"
                    else:
                        user.groups.add(grupo_normal)
                        grupo_usuario = "normal"

                    perfil, _ = PerfilUsuario.objects.get_or_create(
                        user=user,
                        defaults={'oficina': oficina}
                    )

                    total_usuarios_creados += 1
                    info_usuarios.append((username, password, grupo_usuario, oficina.nombre))
                else:
                    info_usuarios.append((username, "(ya existe)", "(sin cambios)", oficina.nombre))

        print(f"Se crearon {total_usuarios_creados} usuarios nuevos.\n")

        print("=== Detalles de todos los usuarios procesados ===")
        print("Username | Password | Grupo | Oficina")
        print("---------------------------------------------------------")

        for username, password, grupo, oficina_str in info_usuarios:
            print(f"{username} | {password} | {grupo} | {oficina_str}")

        print("\n=== Proceso finalizado ===")
