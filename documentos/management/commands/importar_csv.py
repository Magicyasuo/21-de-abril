from django.core.management.base import BaseCommand
import pandas as pd
from datetime import datetime
from documentos.models import RegistroDeArchivo, FUID

class Command(BaseCommand):
    help = "Importa datos desde un archivo Excel a la base de datos y los asocia al FUID con id=1"

    def handle(self, *args, **options):
        print("🔥 Iniciando importación desde Excel...")

        # 📂 Ruta del archivo Excel
        # excel_path = "D:/descargas d/represion/repoproduccion-main/dataUnidad/historias_clinicas/migracion_Inicial.xlsx"
        excel_path = "/home/devsarare/Descargas/10-de-marzo/6-de-marzo-main/dataUnidad/historias_clinicas/formato_de_practica.xlsx"       
 # /home/devsarare/Descargas/10-de-marzo/6-de-marzo-main/dataUnidad/formato de practica .xlsx
    # dataUnidad\historias_clinicas\historias_laborales\Trabajosocial.xlsx
        # 1️⃣ Cargar el archivo
        try:
            df = pd.read_excel(excel_path, sheet_name="formato practica", dtype=str)
            print(f"📊 Excel cargado correctamente con {len(df)} registros.")
        except Exception as e:
            print(f"❌ Error cargando el Excel: {e}")
            return

        # 2️⃣ Limpiar nombres de columnas
        df.columns = df.columns.str.strip()
        df.rename(columns={"codigo_serie_id\n": "codigo_serie_id"}, inplace=True)

        # 3️⃣ Convertir valores booleanos
        def convertir_booleano(valor):
            return 1 if str(valor).strip() in ["1", "true", "sí"] else 0

        df["Estado_archivo"] = df["Estado_archivo"].apply(convertir_booleano)
        df["soporte_fisico"] = df["soporte_fisico"].apply(convertir_booleano)
        df["soporte_electronico"] = df["soporte_electronico"].apply(convertir_booleano)

        # 4️⃣ Convertir fechas
        def convertir_fecha(fecha):
            try:
                return datetime.strptime(fecha.strip(), "%Y-%m-%d") if fecha.strip() else None
            except:
                return None  

        df["fecha_inicial"] = df["fecha_inicial"].apply(convertir_fecha)
        df["fecha_final"] = df["fecha_final"].apply(convertir_fecha)
        df["fecha_creacion"] = df["fecha_creacion"].apply(convertir_fecha)

        # 5️⃣ Convertir valores numéricos
        def convertir_entero(valor):
            try:
                if pd.isna(valor) or str(valor).strip() == "":  # Verifica si es NaN o vacío
                    return 0  # Fuerza el valor a 0
                return int(valor)
            except:
                return 0  # Si hay un error en la conversión, devuelve 0



        columnas_enteros = [
            "id", "numero_orden", "caja", "carpeta", "numero_folios", "cantidad",
            "cantidad_documentos_electronicos", "codigo_serie_id", "codigo_subserie_id",
            "creado_por_id", "identificador_documento"
        ]

        for columna in columnas_enteros:
            if columna in df.columns:
                df[columna] = df[columna].apply(convertir_entero)

        # 6️⃣ Crear los registros de archivo
        registros = [
            RegistroDeArchivo(
                id=row["id"],
                Estado_archivo=row["Estado_archivo"],
                numero_orden=row["numero_orden"],
                codigo=row["codigo"],
                unidad_documental=row["unidad_documental"],
                fecha_inicial=row["fecha_inicial"],
                fecha_final=row["fecha_final"],
                soporte_fisico=row["soporte_fisico"],
                soporte_electronico=row["soporte_electronico"],
                caja=row["caja"],
                carpeta=row["carpeta"],
                tomo_legajo_libro=row["tomo_legajo_libro"],
                numero_folios=row["numero_folios"],
                tipo=row["tipo"],
                cantidad=row["cantidad"],
                ubicacion=row["ubicacion"],
                cantidad_documentos_electronicos=row["cantidad_documentos_electronicos"],
                tamano_documentos_electronicos=row["tamano_documentos_electronicos"],
                notas=row["notas"],
                fecha_creacion=row["fecha_creacion"],
                codigo_serie_id=row["codigo_serie_id"],
                codigo_subserie_id=row["codigo_subserie_id"],
                creado_por_id=row["creado_por_id"],
                identificador_documento=row["identificador_documento"],
            )
            for _, row in df.iterrows()
        ]

        try:
            RegistroDeArchivo.objects.bulk_create(registros)
            print(f"✅ Se han importado {len(registros)} registros correctamente.")
        except Exception as e:
            print(f"❌ Error al insertar los datos: {e}")
            return

        # 7️⃣ Asociar los registros al FUID con id=1
        try:
            fuid = FUID.objects.get(id=2)  # Buscar el FUID con id=1
            registros_ids = RegistroDeArchivo.objects.values_list('id', flat=True)  # Obtener los IDs de los registros importados
            
            fuid.registros.add(*registros_ids)  # Asignar registros al FUID
            print(f"✅ Se han asignado {len(registros)} registros al FUID con id=2.")
        except FUID.DoesNotExist:
            print("❌ Error: No se encontró un FUID con id=2.")
        except Exception as e:
            print(f"❌ Error asignando registros al FUID: {e}")
