import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from faker import Faker
from documentos.models import (
    EntidadProductora, UnidadAdministrativa, OficinaProductora, 
    SerieDocumental, SubserieDocumental, Objeto, PerfilUsuario, 
    RegistroDeArchivo, FichaPaciente # Añade otros modelos si son necesarios
)

# Asegúrate de tener usuarios creados, especialmente un superusuario.
# Puedes crear uno con: python manage.py createsuperuser

class Command(BaseCommand):
    help = 'Puebla la base de datos con datos de ejemplo para la aplicación documentos.'

    def handle(self, *args, **kwargs):
        fake = Faker('es_ES') # Usar localización en español si es posible con Faker

        self.stdout.write("Limpiando datos antiguos (opcional)...")
        # Descomenta si quieres limpiar antes de poblar. ¡CUIDADO EN PRODUCCIÓN!
        # EntidadProductora.objects.all().delete()
        # UnidadAdministrativa.objects.all().delete()
        # OficinaProductora.objects.all().delete()
        # SerieDocumental.objects.all().delete()
        # SubserieDocumental.objects.all().delete()
        # Objeto.objects.all().delete()
        # FichaPaciente.objects.all().delete()
        # RegistroDeArchivo.objects.all().delete()
        # PerfilUsuario.objects.all().delete() # No borrar usuarios generalmente

        self.stdout.write("Creando estructura organizacional...")

        # --- 1. Entidades Productoras ---
        entidades = []
        for _ in range(2): # Crear 2 entidades
            entidad, created = EntidadProductora.objects.get_or_create(
                nombre=fake.company() + " E.S.E."
            )
            entidades.append(entidad)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Creada Entidad: {entidad.nombre}'))

        # --- 2. Unidades Administrativas ---
        unidades = []
        for entidad in entidades:
            for i in range(random.randint(1, 3)): # Crear 1-3 unidades por entidad
                unidad, created = UnidadAdministrativa.objects.get_or_create(
                    nombre=f"Departamento de {fake.job()}",
                    entidad_productora=entidad
                )
                unidades.append(unidad)
                if created:
                    self.stdout.write(self.style.SUCCESS(f'  Creada Unidad: {unidad.nombre} ({entidad.nombre})'))

        # --- 3. Oficinas Productoras ---
        oficinas = []
        for unidad in unidades:
            for i in range(random.randint(1, 4)): # Crear 1-4 oficinas por unidad
                oficina, created = OficinaProductora.objects.get_or_create(
                    nombre=f"Oficina de {fake.bs()}",
                    unidad_administrativa=unidad
                )
                oficinas.append(oficina)
                if created:
                    self.stdout.write(self.style.SUCCESS(f'    Creada Oficina: {oficina.nombre} ({unidad.nombre})'))
        
        # --- 4. Crear Usuarios y Perfiles (Asumiendo que ya existe al menos un superusuario) ---
        # Necesitarás usuarios para asociar registros, FUIDs, etc.
        # Si no tienes usuarios, créalos primero o añade lógica aquí para crearlos.
        users = list(User.objects.all())
        if not users:
            self.stdout.write(self.style.ERROR('No se encontraron usuarios. Por favor, crea al menos un usuario (ej: superusuario) antes de ejecutar este comando.'))
            return # Salir si no hay usuarios

        self.stdout.write("Asignando oficinas a usuarios existentes...")
        for user in users:
             # Asegúrate de que 'perfil' exista en User o crea PerfilUsuario aquí
            if hasattr(user, 'perfil'):
                 # Si ya tiene perfil, quizás no quieras reasignar o actualízalo
                 if user.perfil.oficina is None and oficinas:
                      user.perfil.oficina = random.choice(oficinas)
                      user.perfil.save()
                      self.stdout.write(self.style.SUCCESS(f'Asignada oficina {user.perfil.oficina.nombre} a {user.username}'))
            elif oficinas: # Si no tiene perfil, crea uno
                 perfil, created = PerfilUsuario.objects.get_or_create(
                      user=user,
                      defaults={'oficina': random.choice(oficinas)}
                 )
                 if created:
                      self.stdout.write(self.style.SUCCESS(f'Creado perfil y asignada oficina {perfil.oficina.nombre} a {user.username}'))
        
        # --- 5. Series y Subseries Documentales ---
        self.stdout.write("Creando Series y Subseries...")
        series = []
        codigos_serie_usados = set()
        for _ in range(5): # Crear 5 series
            codigo_s = str(random.randint(100, 999))
            while codigo_s in codigos_serie_usados:
                 codigo_s = str(random.randint(100, 999))
            codigos_serie_usados.add(codigo_s)
            
            serie, created = SerieDocumental.objects.get_or_create(
                codigo=codigo_s,
                defaults={'nombre': f"Serie {fake.catch_phrase()}"}
            )
            series.append(serie)
            if created:
                 self.stdout.write(self.style.SUCCESS(f'Creada Serie: {serie.codigo} - {serie.nombre}'))

            codigos_subserie_usados = set()
            for i in range(random.randint(0, 4)): # Crear 0-4 subseries por serie
                codigo_ss = f"{serie.codigo}.{random.randint(1, 99):02d}"
                while codigo_ss in codigos_subserie_usados:
                    codigo_ss = f"{serie.codigo}.{random.randint(1, 99):02d}"
                codigos_subserie_usados.add(codigo_ss)

                subserie, created = SubserieDocumental.objects.get_or_create(
                    codigo=codigo_ss,
                    serie=serie,
                    defaults={'nombre': f"Subserie {fake.bs()}"}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'  Creada Subserie: {subserie.codigo} - {subserie.nombre}'))

        # --- 6. Objetos ---
        self.stdout.write("Creando Objetos...")
        objetos_base = ["Historias Clínicas", "Contratos", "Actas", "Informes", "Comunicaciones Oficiales"]
        objetos = []
        for nombre_obj in objetos_base:
             obj, created = Objeto.objects.get_or_create(nombre=nombre_obj)
             objetos.append(obj)
             if created:
                  self.stdout.write(self.style.SUCCESS(f'Creado Objeto: {obj.nombre}'))


        # --- 7. Fichas de Pacientes ---
        self.stdout.write("Creando Fichas de Pacientes...")
        pacientes = []
        for i in range(20): # Crear 20 pacientes
            try:
                paciente, created = FichaPaciente.objects.get_or_create(
                    num_identificacion=fake.unique.random_number(digits=10),
                    defaults={
                        'primer_nombre': fake.first_name(),
                        'segundo_nombre': fake.first_name() if random.choice([True, False]) else '',
                        'primer_apellido': fake.last_name(),
                        'segundo_apellido': fake.last_name() if random.choice([True, False]) else '',
                        'fecha_nacimiento': fake.date_of_birth(minimum_age=0, maximum_age=90),
                        'Numero_historia_clinica': fake.unique.random_number(digits=8),
                        'caja': f"C{random.randint(1, 100):03d}",
                        'carpeta': f"CP{random.randint(1, 500):04d}",
                        'tipo_identificacion': random.choice(['Cedula de Ciudadania', 'Tarjeta de Identidad', 'Registro Civil', 'Pasaporte']),
                        'sexo': random.choice(['Masculino', 'Femenino', 'Otro']),
                        'activo': True,
                    }
                )
                pacientes.append(paciente)
                if created:
                     self.stdout.write(self.style.SUCCESS(f'Creada Ficha Paciente: {paciente.num_identificacion} - {paciente.primer_nombre} {paciente.primer_apellido}'))
            except Exception as e: # Captura errores de unicidad u otros
                 self.stdout.write(self.style.WARNING(f'No se pudo crear paciente {i+1}: {e}'))


        # --- 8. Registros de Archivo ---
        self.stdout.write("Creando Registros de Archivo...")
        registros = []
        if not series:
             self.stdout.write(self.style.ERROR('No hay series documentales para crear registros.'))
             return
        
        for i in range(50): # Crear 50 registros
            serie_sel = random.choice(series)
            subseries_de_serie = list(SubserieDocumental.objects.filter(serie=serie_sel))
            subserie_sel = random.choice(subseries_de_serie) if subseries_de_serie else None
            creador = random.choice(users)
            paciente_asociado = random.choice(pacientes) if pacientes and random.random() < 0.7 else None # 70% de asociar paciente

            try:
                registro, created = RegistroDeArchivo.objects.get_or_create(
                    numero_orden=i + 1, # Asignar un número de orden simple
                    defaults={
                        'codigo_serie': serie_sel,
                        'codigo_subserie': subserie_sel,
                        'unidad_documental': f"{random.choice(['Informe', 'Acta', 'Historia', 'Contrato', 'Comunicado'])} - {fake.sentence(nb_words=4)}",
                        'fecha_inicial': fake.date_between(start_date='-5y', end_date='today'),
                        'fecha_final': fake.date_between(start_date='-5y', end_date='today'),
                        'soporte_fisico': random.choice([True, False]),
                        'soporte_electronico': random.choice([True, False]),
                        'caja': random.randint(1, 100) if random.choice([True, False]) else None,
                        'carpeta': random.randint(1, 500) if random.choice([True, False]) else None,
                        'numero_folios': random.randint(1, 200) if random.choice([True, False]) else None,
                        'identificador_documento': paciente_asociado.Numero_historia_clinica if paciente_asociado else None,
                        'notas': fake.text(max_nb_chars=150) if random.random() < 0.5 else '',
                        'creado_por': creador,
                    }
                )
                registros.append(registro)
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Creado Registro: {registro.numero_orden} - Serie: {registro.codigo_serie.codigo}'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'No se pudo crear registro {i+1}: {e}'))
        
        # --- Pasos Adicionales (Pendientes) ---
        # - Crear instancias de FUID y asociarlas a registros
        # - Crear instancias de Documento (sin subir archivos reales por ahora)
        # - Crear PermisoUsuarioSerie si es necesario

        self.stdout.write(self.style.SUCCESS('¡Población de datos básicos completada!')) 