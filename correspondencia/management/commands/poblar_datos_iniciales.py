import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings

try:
    from documentos.models import EntidadProductora, UnidadAdministrativa, OficinaProductora, SerieDocumental, SubserieDocumental
except ImportError:
    raise CommandError("No se pudieron importar los modelos desde 'documentos.models'.")

CSV_FILENAME = 'Unitdadtotalitaria.csv'

class Command(BaseCommand):
    help = f'Puebla la base de datos con datos iniciales desde {CSV_FILENAME}'

    def handle(self, *args, **options):
        csv_filepath = os.path.join(settings.BASE_DIR, CSV_FILENAME)

        if not os.path.exists(csv_filepath):
            raise CommandError(f"Archivo '{CSV_FILENAME}' no encontrado en {settings.BASE_DIR}")

        self.stdout.write(f"Iniciando población desde {csv_filepath}...")

        entidades_map = {}
        unidades_map = {}
        series_map = {}
        current_section = None
        row_num = 0 # Initialize row_num

        try:
            with open(csv_filepath, mode='r', encoding='utf-8') as file:
                reader = csv.reader(file)
                with transaction.atomic():
                    for row_num, row in enumerate(reader, 1):
                        if not row or not any(field.strip() for field in row): # Skip empty or effectively empty rows
                            continue

                        line_content = "".join(row).strip().upper()
                        if line_content == 'ENTIDADPRODUCTORA':
                            current_section = 'ENTIDAD'
                            self.stdout.write("Procesando sección ENTIDAD...")
                            continue
                        elif line_content == 'UNIDAD':
                            current_section = 'UNIDAD'
                            self.stdout.write("Procesando sección UNIDAD...")
                            continue
                        elif line_content == 'OFICINA':
                            current_section = 'OFICINA'
                            self.stdout.write("Procesando sección OFICINA...")
                            continue
                        elif line_content == 'SERIE':
                            current_section = 'SERIE'
                            self.stdout.write("Procesando sección SERIE...")
                            continue
                        elif line_content == 'SUBSERIE':
                            current_section = 'SUBSERIE'
                            self.stdout.write("Procesando sección SUBSERIE...")
                            continue
                        elif line_content in ['OBJETO']:
                             current_section = None
                             continue

                        # --- Process rows based on section --- 
                        if current_section == 'ENTIDAD':
                             if len(row) >= 2 and row[0].strip().isdigit():
                                csv_id, nombre = int(row[0].strip()), row[1].strip()
                                obj, created = EntidadProductora.objects.get_or_create(nombre=nombre)
                                entidades_map[csv_id] = obj
                                if created: self.stdout.write(f"  Creada Entidad: {nombre}")
                             else:
                                self.stdout.write(self.style.WARNING(f"Línea {row_num}: Formato Entidad inválido {row}"))

                        elif current_section == 'UNIDAD':
                            # ASUNCIÓN: Todas las unidades pertenecen a la primera entidad encontrada
                            if not entidades_map:
                                self.stdout.write(self.style.ERROR(f"Línea {row_num}: No se encontró Entidad Productora para asociar Unidad '{row[1] if len(row)>1 else '??'}\'" ))
                                continue
                            # Usar la primera (y asumimos única) entidad
                            entidad_obj = list(entidades_map.values())[0]

                            if len(row) >= 2 and row[0].strip().isdigit():
                                csv_id, nombre = int(row[0].strip()), row[1].strip()
                                # entidad_csv_id = int(row[2].strip()) # Ignoramos este ID

                                obj, created = UnidadAdministrativa.objects.get_or_create(
                                    nombre=nombre,
                                    entidad_productora=entidad_obj,
                                    defaults={}
                                )
                                unidades_map[csv_id] = obj
                                if created: self.stdout.write(f"  Creada Unidad: {nombre} (Asociada a: {entidad_obj.nombre}) ")
                            else:
                                self.stdout.write(self.style.WARNING(f"Línea {row_num}: Formato Unidad inválido {row}"))

                        elif current_section == 'OFICINA':
                            if len(row) >= 3 and row[0].strip().isdigit() and row[2].strip().isdigit():
                                csv_id, nombre, unidad_csv_id_from_csv = int(row[0].strip()), row[1].strip(), int(row[2].strip())

                                # Buscar la unidad usando el ID del CSV mapeado
                                unidad_obj = unidades_map.get(unidad_csv_id_from_csv)

                                if unidad_obj:
                                    obj, created = OficinaProductora.objects.get_or_create(
                                        nombre=nombre,
                                        unidad_administrativa=unidad_obj,
                                        defaults={}
                                    )
                                    if created: self.stdout.write(f"  Creada Oficina: {nombre} (Asociada a: {unidad_obj.nombre}) ")
                                else:
                                     self.stdout.write(self.style.ERROR(f"Línea {row_num}: Unidad ID {unidad_csv_id_from_csv} NO ENCONTRADA en el mapa para Oficina '{nombre}\'" ))
                            else:
                                self.stdout.write(self.style.WARNING(f"Línea {row_num}: Formato Oficina inválido {row}"))

                        elif current_section == 'SERIE':
                            # Check if the row has enough elements and the first element is a digit
                            if len(row) >= 3 and row[0].strip().isdigit():
                                try:
                                    csv_id_grande = int(row[0].strip())
                                    codigo_corto = row[1].strip()
                                    nombre = row[2].strip()
                                    
                                    # Use update_or_create to handle existing codes with potentially different names
                                    obj, created = SerieDocumental.objects.update_or_create(
                                        codigo=codigo_corto, 
                                        defaults={'nombre': nombre}
                                    )
                                    series_map[csv_id_grande] = obj
                                    if created:
                                        self.stdout.write(f"  Creada Serie (código {codigo_corto}): {nombre}")
                                    else:
                                        self.stdout.write(f"  Actualizada/Verificada Serie (código {codigo_corto}): {nombre}")
                                except ValueError:
                                    self.stdout.write(self.style.WARNING(f"Línea {row_num}: ID grande de Serie inválido {row[0]}"))
                                except IndexError:
                                     self.stdout.write(self.style.WARNING(f"Línea {row_num}: Faltan datos en fila Serie {row}"))
                            else:
                                self.stdout.write(self.style.WARNING(f"Línea {row_num}: Formato Serie inválido {row}"))

                        elif current_section == 'SUBSERIE':
                            if len(row) >= 4 and row[3].strip().isdigit():
                                try:
                                    # csv_id_grande = int(row[0].strip()) # No necesitamos el ID de la subserie
                                    codigo_corto = row[1].strip()
                                    nombre = row[2].strip()
                                    serie_csv_id_grande = int(row[3].strip())
                                    
                                    serie_obj = series_map.get(serie_csv_id_grande)
                                    if serie_obj:
                                        obj, created = SubserieDocumental.objects.update_or_create(
                                            codigo=codigo_corto,
                                            serie=serie_obj,
                                            defaults={'nombre': nombre}
                                        )
                                        if created:
                                            self.stdout.write(f"  Creada Subserie (código {codigo_corto}): {nombre} -> Serie: {serie_obj.nombre}")
                                        else:
                                             self.stdout.write(f"  Actualizada/Verificada Subserie (código {codigo_corto}): {nombre}")
                                    else:
                                         self.stdout.write(self.style.ERROR(f"Línea {row_num}: Serie ID grande {serie_csv_id_grande} no encontrada para Subserie '{nombre}'"))
                                except ValueError:
                                    self.stdout.write(self.style.WARNING(f"Línea {row_num}: ID grande de Serie inválido {row[3]} para Subserie"))
                                except IndexError:
                                     self.stdout.write(self.style.WARNING(f"Línea {row_num}: Faltan datos en fila Subserie {row}"))
                            else:
                                self.stdout.write(self.style.WARNING(f"Línea {row_num}: Formato Subserie inválido {row}"))

        except FileNotFoundError:
             raise CommandError(f"Archivo '{csv_filepath}' no encontrado.")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error procesando archivo en línea ~{row_num}: {e}"))
            self.stdout.write(traceback.format_exc()) # Print full traceback for debugging
            raise CommandError(f"Población fallida. Error: {e}")

        self.stdout.write(self.style.SUCCESS("Población de datos iniciales completada con éxito.")) 