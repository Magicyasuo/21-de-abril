import os
import django
import pandas as pd
from datetime import datetime

print("🔥 El script ha iniciado...")

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hospital_document_management.settings')
django.setup()

print("✅ Django está configurado.")

# Intentar importar el modelo
try:
    from documentos.models import RegistroDeArchivo
    print("✅ Modelo 'RegistroDeArchivo' importado correctamente.")
except Exception as e:
    print(f"❌ Error importando modelo: {e}")

# Probar conexión a la base de datos
from django.db import connection

try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    print("✅ Conexión a la base de datos exitosa.")
except Exception as e:
    print(f"❌ Error en la conexión a la base de datos: {e}")

# Ruta del archivo CSV
csv_path = "D:/descargas d/represion/repoproduccion-main/dataUnidad/historias_clinicas_1.csv"

if os.path.exists(csv_path):
    print(f"📂 Archivo CSV encontrado: {csv_path}")
else:
    print(f"❌ Archivo NO encontrado en {csv_path}. Verifica la ruta.")

# Leer el CSV
try:
    df = pd.read_csv(csv_path, delimiter=',', dtype=str)
    print(f"📊 CSV cargado correctamente con {len(df)} registros.")
except Exception as e:
    print(f"❌ Error cargando el CSV: {e}")

print("✅ Finalización del script.")
