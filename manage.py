#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "hospital_document_management.settings"
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()



    








#     registro = RegistroDeArchivo.objects.first()
# print(registro.id)  # Mostrará el valor del campo id

# ......................
#     import os

# output_file = "contenido_proyecto.txt"

# with open(output_file, "w", encoding="utf-8") as f:
#     for root, dirs, files in os.walk("."):
#         for file in files:
#             file_path = os.path.join(root, file)
#             f.write(f"### {file_path} ###\n")
#             try:
#                 with open(file_path, "r", encoding="utf-8") as code_file:
#                     f.write(code_file.read())
#             except Exception as e:
#                 f.write(f"[Error al leer el archivo: {e}]\n")
#             f.write("\n\n")
# print(f"Todo el contenido del proyecto ha sido exportado a {output_file}")

