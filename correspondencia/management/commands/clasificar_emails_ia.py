# correspondencia/management/commands/clasificar_emails_ia.py

import traceback
import os
import json
from collections import defaultdict # Para agrupar subseries por serie
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Q, Prefetch # Para optimizar consulta
from django.utils import timezone # Necesario para fecha_clasificacion
# Importar la biblioteca de OpenAI
from openai import OpenAI

# Modelos de Django
from correspondencia.models import CorreoEntrante, OficinaProductora, SerieDocumental, SubserieDocumental

# --- CONFIGURACIÓN OPENAI (MANTENER ADVERTENCIA API KEY) ---
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', "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")
MODELO_OPENAI = "gpt-4o"

# --- Diccionarios para mapeo y relaciones ---
oficinas_map = {}
series_map = {}
subseries_map = {} # Mapeo de nombre de subserie a su objeto
series_con_subseries = defaultdict(list) # Diccionario: serie_nombre -> [lista de nombres de sus subseries]

class Command(BaseCommand):
    help = f'Clasifica correos entrantes (Oficina, Serie y Subserie) usando la API de OpenAI ({MODELO_OPENAI}).'

    def _load_labels_and_maps(self):
        """Carga etiquetas y crea mapeos, incluyendo la relación Serie -> Subserie."""
        global oficinas_map, series_map, subseries_map, series_con_subseries
        self.stdout.write("Cargando etiquetas y relaciones desde la base de datos...")
        try:
            oficinas = OficinaProductora.objects.all()
            # CORRECCIÓN FINAL: Usar el related_name por defecto de Django
            series = SerieDocumental.objects.prefetch_related('subseriedocumental_set')

            oficinas_labels = [o.nombre for o in oficinas]
            series_labels = [s.nombre for s in series]
            # Crear lista plana de todas las subseries para el prompt inicial
            todas_subseries_labels = list(SubserieDocumental.objects.values_list('nombre', flat=True).distinct())

            oficinas_map = {o.nombre: o.pk for o in oficinas}
            series_map = {s.nombre: s.pk for s in series}
            subseries_map = {sub.nombre: sub for sub in SubserieDocumental.objects.all()} # Guardar objeto completo

            # Construir el diccionario series_con_subseries
            series_con_subseries.clear()
            for serie in series:
                # CORRECCIÓN FINAL: Usar el related_name por defecto al acceder
                nombres_subseries = [sub.nombre for sub in serie.subseriedocumental_set.all()]
                if nombres_subseries: # Solo añadir si tiene subseries
                    series_con_subseries[serie.nombre] = nombres_subseries

            if not oficinas_labels:
                 self.stdout.write(self.style.WARNING("No se encontraron oficinas productoras."))
                 oficinas_labels = []
            if not series_labels:
                 self.stdout.write(self.style.WARNING("No se encontraron series documentales."))
                 series_labels = []
            if not todas_subseries_labels:
                 self.stdout.write(self.style.WARNING("No se encontraron subseries documentales."))
                 todas_subseries_labels = []

            self.stdout.write(f"Etiquetas cargadas - Oficinas: {len(oficinas_labels)}, Series: {len(series_labels)}, Subseries (total): {len(todas_subseries_labels)}")
            # Opcional: imprimir estructura de series_con_subseries para verificar
            # self.stdout.write(f"Relación Serie->Subserie: {dict(series_con_subseries)}")
            return oficinas_labels, series_labels, todas_subseries_labels

        except AttributeError as ae:
             # Capturar específicamente el AttributeError para dar un mensaje más útil
             self.stdout.write(self.style.ERROR(f"Error de Atributo obteniendo etiquetas/relaciones: {ae}"))
             self.stdout.write(self.style.ERROR("--> Verifica que el 'related_name' en el modelo SubserieDocumental (campo 'serie') sea correcto y se use aquí."))
             print(traceback.format_exc())
             raise # Detener ejecución
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error crítico obteniendo etiquetas/relaciones: {e}"))
            print(traceback.format_exc())
            raise

    def handle(self, *args, **options):
        self.stdout.write(f"Iniciando clasificación IA con modelo OpenAI: {MODELO_OPENAI}")

        # Verificar API Key
        if not OPENAI_API_KEY or "sk-proj" not in OPENAI_API_KEY: # Simple check
             self.stdout.write(self.style.ERROR("Error: La API Key de OpenAI no parece estar configurada correctamente."))
             self.stdout.write(self.style.ERROR("Asegúrate de establecer la variable de entorno OPENAI_API_KEY."))
             return

        # Configurar cliente OpenAI
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            client.models.list() # Probar conexión
            self.stdout.write(self.style.SUCCESS("Cliente OpenAI configurado y conexión exitosa."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error configurando/conectando con OpenAI: {e}"))
            self.stdout.write(self.style.ERROR("Verifica tu API Key, la conexión a internet y los permisos."))
            print(traceback.format_exc())
            return

        # Cargar etiquetas y relaciones
        try:
            oficinas_labels, series_labels, todas_subseries_labels = self._load_labels_and_maps()
            if not oficinas_labels or not series_labels: # Subseries puede estar vacía
                self.stdout.write(self.style.ERROR("No se pudieron cargar las etiquetas de Oficina o Serie. Abortando."))
                return
        except Exception:
             # El error ya se mostró en _load_labels_and_maps
             return

        # Obtener correos pendientes
        correos_pendientes = CorreoEntrante.objects.filter(procesado=False).order_by('fecha_lectura_imap')
        total_pendientes = correos_pendientes.count()
        self.stdout.write(f"Se encontraron {total_pendientes} correos pendientes de clasificación.")

        if total_pendientes == 0:
            self.stdout.write("No hay correos nuevos para clasificar.")
            return

        clasificados_ok = 0
        errores_clasificacion = 0

        for i, correo in enumerate(correos_pendientes):
            self.stdout.write(f"\n--- Procesando Correo {i+1}/{total_pendientes} (ID: {correo.id}, Message-ID: {correo.message_id}) ---")
            self.stdout.write(f"De: {correo.remitente}, Asunto: {correo.asunto}")

            # Preparar texto (incluyendo adjuntos)
            adjuntos_info = ""
            if correo.adjuntos.exists():
                 nombres_adjuntos = [a.nombre_original for a in correo.adjuntos.all()[:5]]
                 adjuntos_info = f"\nNombres de archivos adjuntos (primeros 5): {', '.join(nombres_adjuntos)}"
            texto_a_clasificar = (
                f"Remitente: {correo.remitente}\n"
                f"Asunto: {correo.asunto}\n"
                f"{adjuntos_info}\n\n"
                f"Cuerpo (primeros 2000 caracteres):\n{correo.cuerpo_texto[:2000]}"
            )

            if not texto_a_clasificar.strip():
                 self.stdout.write(self.style.WARNING("  Correo vacío. Marcando como procesado y saltando."))
                 correo.procesado = True
                 correo.fecha_clasificacion = timezone.now()
                 correo.save(update_fields=['procesado', 'fecha_clasificacion'])
                 continue

            # --- Construir el NUEVO prompt con Subserie ---
            prompt = f"""
Eres un asistente experto en clasificación de correspondencia para un hospital.
Tu tarea es analizar el siguiente correo electrónico y clasificarlo según TRES criterios: Oficina Productora Destino, Serie Documental y Subserie Documental.

**Correo a clasificar:**
---
{texto_a_clasificar}
---

**Opciones de clasificación disponibles:**
*   **Oficinas Productoras Destino:** {', '.join(oficinas_labels)}
*   **Series Documentales:** {', '.join(series_labels)}
*   **Subseries Documentales (TODAS):** {', '.join(todas_subseries_labels) if todas_subseries_labels else '(Ninguna definida)'}

**IMPORTANTE: Relación Serie -> Subserie**
Una Subserie SÓLO es válida si pertenece a la Serie que has elegido. A continuación se muestra qué Subseries pertenecen a cada Serie (si una Serie no aparece, no tiene Subseries definidas):
{json.dumps(dict(series_con_subseries), indent=2, ensure_ascii=False)}

**Instrucciones:**
1.  Lee cuidadosamente el contenido del correo.
2.  Elige la **Oficina Productora Destino** MÁS PROBABLE de la lista proporcionada.
3.  Elige la **Serie Documental** MÁS PROBABLE de la lista proporcionada.
4.  Basándote en la Serie elegida en el paso 3, elige la **Subserie Documental** MÁS PROBABLE de la lista de Subseries que pertenecen a esa Serie (consulta la relación Serie -> Subserie).
5.  Si la Serie elegida no tiene Subseries definidas o ninguna Subserie parece adecuada, responde con `null` para la subserie.
6.  Responde ÚNICAMENTE con un objeto JSON válido que contenga las tres clasificaciones, usando las claves: "oficina_productora", "serie_documental", "subserie_documental".

**Ejemplo de formato de respuesta JSON esperado (con subserie):**
{{
  "oficina_productora": "Talento Humano",
  "serie_documental": "HISTORIAS LABORALES",
  "subserie_documental": "CONTRATOS"
}}

**Ejemplo de formato de respuesta JSON esperado (sin subserie aplicable):**
{{
  "oficina_productora": "Facturación",
  "serie_documental": "FACTURAS",
  "subserie_documental": null
}}

Proporciona SOLO el objeto JSON como respuesta.
"""

            oficina_pred_obj = None
            serie_pred_obj = None
            subserie_pred_obj = None # Añadido
            error_en_correo = False

            try:
                self.stdout.write("  Enviando a API OpenAI para clasificación (Oficina, Serie, Subserie)...")
                response = client.chat.completions.create(
                    model=MODELO_OPENAI,
                    messages=[
                        {"role": "system", "content": "Eres un asistente experto en clasificación de correspondencia hospitalaria."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=200, # Aumentar un poco por la subserie
                    response_format={ "type": "json_object" }
                )

                respuesta_json_str = response.choices[0].message.content
                self.stdout.write(f"  Respuesta API (raw): {respuesta_json_str}")

                clasificacion = json.loads(respuesta_json_str)

                # Extraer predicciones
                nombre_oficina = clasificacion.get('oficina_productora')
                nombre_serie = clasificacion.get('serie_documental')
                nombre_subserie = clasificacion.get('subserie_documental') # Puede ser null

                if not nombre_oficina or not nombre_serie: # Subserie puede ser null
                     self.stdout.write(self.style.ERROR("  Respuesta JSON incompleta (falta oficina o serie)."))
                     error_en_correo = True
                else:
                    self.stdout.write(f"    -> Predicción Oficina: {nombre_oficina}")
                    self.stdout.write(f"    -> Predicción Serie: {nombre_serie}")
                    self.stdout.write(f"    -> Predicción Subserie: {nombre_subserie if nombre_subserie else '(Ninguna)'}")

                    # --- Validación Oficina ---
                    try:
                        oficina_pk = oficinas_map.get(nombre_oficina)
                        if oficina_pk:
                             oficina_pred_obj = OficinaProductora.objects.get(pk=oficina_pk)
                        else:
                             self.stdout.write(self.style.WARNING(f"    Nombre de oficina '{nombre_oficina}' no encontrado en mapeo. No se asignará."))
                    except OficinaProductora.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f"    ¡ERROR BD! Oficina '{nombre_oficina}' NO EXISTE."))
                        error_en_correo = True
                    except Exception as e_db:
                         self.stdout.write(self.style.ERROR(f"    Error DB buscando oficina '{nombre_oficina}': {e_db}"))
                         error_en_correo = True

                    # --- Validación Serie ---
                    if not error_en_correo: # Solo si la oficina está ok (o no es crítica)
                        try:
                            serie_pk = series_map.get(nombre_serie)
                            if serie_pk:
                                 serie_pred_obj = SerieDocumental.objects.get(pk=serie_pk)
                            else:
                                 self.stdout.write(self.style.WARNING(f"    Nombre de serie '{nombre_serie}' no encontrado en mapeo. No se asignará."))
                        except SerieDocumental.DoesNotExist:
                            self.stdout.write(self.style.ERROR(f"    ¡ERROR BD! Serie '{nombre_serie}' NO EXISTE."))
                            error_en_correo = True
                        except Exception as e_db:
                             self.stdout.write(self.style.ERROR(f"    Error DB buscando serie '{nombre_serie}': {e_db}"))
                             error_en_correo = True

                    # --- Validación Subserie (dependiente de la Serie) ---
                    if not error_en_correo and serie_pred_obj and nombre_subserie:
                        # Verificar si la subserie existe y pertenece a la serie predicha
                        subseries_validas_para_serie = series_con_subseries.get(serie_pred_obj.nombre, [])
                        if nombre_subserie in subseries_validas_para_serie:
                            try:
                                # Obtener el objeto Subserie desde el mapa
                                subserie_pred_obj = subseries_map.get(nombre_subserie)
                                if not subserie_pred_obj:
                                     # Fallback por si el mapa falló (raro)
                                     subserie_pred_obj = SubserieDocumental.objects.get(nombre=nombre_subserie, serie=serie_pred_obj)
                            except SubserieDocumental.DoesNotExist:
                                 self.stdout.write(self.style.ERROR(f"    ¡ERROR BD! Subserie '{nombre_subserie}' existe pero no se encontró ligada a Serie '{serie_pred_obj.nombre}'."))
                                 # No marcar error_en_correo aquí? Opcional. Dejarla sin asignar.
                                 nombre_subserie = None # Anularla si no se encuentra
                                 subserie_pred_obj = None
                            except Exception as e_db:
                                 self.stdout.write(self.style.ERROR(f"    Error DB buscando subserie '{nombre_subserie}': {e_db}"))
                                 # No marcar error_en_correo aquí? Opcional. Dejarla sin asignar.
                                 nombre_subserie = None
                                 subserie_pred_obj = None
                        else:
                            self.stdout.write(self.style.WARNING(f"    Subserie predicha '{nombre_subserie}' NO es válida para la Serie '{serie_pred_obj.nombre}'. No se asignará."))
                            subserie_pred_obj = None # Asegurar que no se guarde
                    elif nombre_subserie:
                         # Si hay error previo o no se encontró la serie, no se puede validar la subserie
                         self.stdout.write(self.style.WARNING(f"    No se pudo validar/asignar la subserie '{nombre_subserie}' debido a errores previos o falta de serie."))
                         subserie_pred_obj = None


                    # --- Guardar Resultados --- 
                    if not error_en_correo: # Solo si las validaciones críticas (Oficina, Serie) pasaron
                        correo.oficina_clasificada = oficina_pred_obj
                        correo.serie_clasificada = serie_pred_obj
                        correo.subserie_clasificada = subserie_pred_obj # Guardar obj subserie (puede ser None)
                        correo.procesado = True
                        correo.fecha_clasificacion = timezone.now()
                        correo.save(update_fields=[
                            'oficina_clasificada', 'serie_clasificada', 'subserie_clasificada',
                            'procesado', 'fecha_clasificacion'
                        ])
                        self.stdout.write(self.style.SUCCESS(
                            f"  Correo ID {correo.id} clasificado y guardado "
                            f"(Oficina: {oficina_pred_obj}, Serie: {serie_pred_obj}, Subserie: {subserie_pred_obj})."
                        ))
                        clasificados_ok += 1
                    else:
                         # Marcar procesado sin clasificación si hubo error crítico
                         correo.procesado = True
                         correo.fecha_clasificacion = timezone.now()
                         correo.save(update_fields=['procesado', 'fecha_clasificacion'])
                         self.stdout.write(self.style.WARNING(f"  Correo ID {correo.id} marcado como procesado pero SIN clasificación debido a errores."))
                         errores_clasificacion += 1


            except json.JSONDecodeError:
                 self.stdout.write(self.style.ERROR(f"  Error parseando JSON de OpenAI: {respuesta_json_str}"))
                 errores_clasificacion += 1
                 correo.procesado = True
                 correo.fecha_clasificacion = timezone.now()
                 correo.save(update_fields=['procesado', 'fecha_clasificacion'])
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error inesperado clasificando correo ID {correo.id}: {e}"))
                print(traceback.format_exc())
                errores_clasificacion += 1
                correo.procesado = True
                correo.fecha_clasificacion = timezone.now()
                correo.save(update_fields=['procesado', 'fecha_clasificacion'])


        self.stdout.write(self.style.SUCCESS(f"\n--- Clasificación IA con OpenAI completada ---"))
        self.stdout.write(f"Correos clasificados exitosamente: {clasificados_ok}")
        self.stdout.write(f"Correos con errores durante clasificación (marcados como procesados): {errores_clasificacion}")
        pendientes_final = CorreoEntrante.objects.filter(procesado=False).count()
        self.stdout.write(f"Correos restantes pendientes: {pendientes_final}") 