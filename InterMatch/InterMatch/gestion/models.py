from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

class UsuarioManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El usuario debe tener un correo electrónico')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, email, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    usuario_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    tipo_doc = models.CharField(max_length=20)
    num_doc = models.CharField(max_length=20)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=30, unique=True)
    password = models.CharField(max_length=128)
    rol = models.CharField(max_length=20, blank=True)
    fecha_registro = models.DateField()

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'nombre', 'apellido', 'num_doc']

    objects = UsuarioManager()

    def __str__(self):
        return self.username

    class Meta:
        db_table = 'usuario'


class Rubro(models.Model):
    rubro_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'rubro'

    def __str__(self):
        return self.nombre

class Certificacion(models.Model):
    certificacion_id = models.AutoField(primary_key= True)
    nombre = models.CharField(max_length=50)

    class Meta:
        db_table = 'certificacion'

    def __str__(self):
        return self.nombre
    
class EmpresaCertificacion(models.Model):
    empresa = models.ForeignKey('EmpresaExportadora', db_column='empresa_id', on_delete=models.CASCADE)
    certificacion = models.ForeignKey(Certificacion, on_delete=models.CASCADE)

    class Meta:
        db_table = 'empresaexportadora_certificaciones'
        unique_together = ('empresa', 'certificacion')


class Pais(models.Model):
    nombre = models.CharField(max_length=100)
    def __str__(self):
        return self.nombre

class Provincia(models.Model):
    nombre = models.CharField(max_length=100)
    pais = models.ForeignKey(Pais, on_delete=models.CASCADE)
    def __str__(self):
        return self.nombre

class Localidad(models.Model):
    nombre = models.CharField(max_length=100)
    provincia = models.ForeignKey(Provincia, on_delete=models.CASCADE)
    def __str__(self):
        return self.nombre


class EmpresaPais(models.Model):
    empresa = models.ForeignKey('EmpresaExportadora', db_column='empresa_id', on_delete=models.CASCADE)
    pais = models.ForeignKey(Pais, on_delete=models.CASCADE)

    class Meta:
        db_table = 'empresaexportadora_paises_exporta'
        unique_together = ('empresa', 'pais')

class PrefijoTelefono(models.Model):
    codigo = models.CharField(max_length=5, unique=True, verbose_name="Codigo")
    pais = models.CharField(max_length=50, verbose_name="Pais")

    def __str__(self):
        return f"{self.codigo} ({self.pais})"

class UnidadMedida(models.Model):
    nombre = models.CharField(max_length=50, unique= True)
    def __str__ (self): return self.nombre    

class EmpresaExportadora(models.Model):
    empresa_id = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE)
    razon_social = models.CharField(max_length=100)
    cargo = models.CharField(max_length=50)
    rubro = models.ForeignKey(Rubro, on_delete=models.CASCADE)
    prefijo_telefono = models.ForeignKey(PrefijoTelefono, on_delete=models.SET_NULL, null=True, blank=True)
    telefono = models.CharField(max_length=20, verbose_name="Numero de Telefono")
    provincia = models.ForeignKey(Provincia, on_delete=models.CASCADE)
    localidad = models.ForeignKey(Localidad, on_delete=models.CASCADE)
    sitio_web = models.URLField(blank=True, null=True)
    brochure = models.FileField(upload_to='brochures/')
    logo = models.ImageField(
        upload_to='logos/',
        default='logos/default_logo.jpg',
        blank= True,
        null= True
    )
    capacidad_productiva = models.IntegerField(db_column='capacidad_mensual')
    unidad_capacidad = models.ForeignKey(
        UnidadMedida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="empresas"
    )

    certificaciones = models.ManyToManyField(
        Certificacion,
        through='EmpresaCertificacion'
    )
    paises_exporta = models.ManyToManyField(
        Pais,
        through='EmpresaPais',
        blank=True
    )

    exporta_actualmente = models.CharField(max_length=2, choices=[('Sí', 'Sí'), ('No', 'No')])
    comentarios = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'empresaexportadora'

    def clean(self):
        super().clean()
        if self.capacidad_productiva is not None and self.unidad_capacidad is None:
            raise ValidationError("Selecciona una unidad de medida.")
        if self.unidad_capacidad and self.unidad_capacidad.nombre == "N/A" and self.capacidad_productiva:
            pass

    def __str__(self):
        return self.razon_social or f"Empresa {self.pk}"

TIPO_IMPORTADOR_CHOICES = [
    ('distribuidor_mayorista', 'Distribuidor Mayorista'),
    ('distribuidor_minorista', 'Distribuidor Minorista'),
    ('retail', 'Retailer / Cadena comercial'),
    ('e_comerce', 'E-commerce'),
    ('broker', 'Broker / Agente comercial'),
    ('otro', 'Otro'),
]

CARGO_CHOICES = [
    ('dueno_fundador', 'Dueño / Fundador'),
    ('gerente_general', 'Gerente General'),
    ('director_compras', 'Director de Compras'),
    ('resp_importaciones', 'Responsable de Importaciones'),
    ('jefe_logistica', 'Jefe de Logística'),
    ('asistente_comercial', 'Asistente Comercial'),
    ('encargado_proveedores', 'Encargado de Proveedores'),
    ('otro', 'Otro'),
]

class Importador(models.Model):
    usuario = models.OneToOneField('Usuario', on_delete=models.CASCADE, related_name='importador')
    pais_origen = models.ForeignKey('Pais', on_delete=models.PROTECT)
    provincia = models.ForeignKey('Provincia', on_delete=models.PROTECT)
    localidad = models.ForeignKey('Localidad', on_delete=models.PROTECT)
    idiomas = models.ManyToManyField('Idioma', blank=True)
    rubros = models.ManyToManyField('Rubro', blank=True)
    paises_comercializa = models.ManyToManyField('Pais', related_name='importadores_que_comercializan', blank=True)
    tipos_proveedor = models.ManyToManyField('TipoProveedor', blank=True)


    razon_social = models.CharField(max_length=150)
    cargo = models.CharField(max_length=100, choices=CARGO_CHOICES)
    prefijo_telefono = models.ForeignKey(PrefijoTelefono, on_delete=models.SET_NULL, null=True, blank=True)
    telefono = models.CharField(max_length=20, verbose_name="Numero de Telefono")
    RANGO_EMPLEADOS = [
    ('1-10', '1 a 10'),
    ('11-50', '11 a 50'),
    ('51-200', '51 a 200'),
    ('200+', 'Más de 200'),
    ]

    empleados = models.CharField(max_length=10, choices=RANGO_EMPLEADOS)

    sitio_web = models.URLField(blank=True, null=True)
    logo = models.ImageField(
        upload_to='logos/',
        default='logos/default_logo.jpg',
        blank= True,
        null= True
    )

    tipo_importador = models.CharField(max_length=50, choices=TIPO_IMPORTADOR_CHOICES)

    experiencia_proveedores_arg = models.BooleanField()
    presentacion_buscada = models.CharField(
        max_length=20,
        choices=[
            ('A granel', 'A granel'),
            ('Fraccionado', 'Fraccionado'),
            ('Ambos', 'Ambos'),
            ('No aplica', 'No aplica'),
        ]
    )
    comentarios = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.razon_social or f"Importador {self.pk}"

class Idioma(models.Model):
    nombre = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre

class TipoProveedor(models.Model):
    nombre = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre


class PeriodoInscripcion(models.Model):
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    activo = models.BooleanField(default=False)

    def __str__(self):
        return f"Periodo: {self.fecha_inicio} a {self.fecha_fin}"

class HorarioDisponible(models.Model):
    hora = models.TimeField(unique=True)

    def __str__(self):
        return self.hora.strftime('%H:%M')

class FechaDisponible(models.Model):
    fecha = models.DateField(unique=True)
    habilitada = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        if self.habilitada:
            limite = getattr(settings, "MAX_FECHAS_HABILATADAS", 2)
            qs = FechaDisponible.objects.filter(habilitada= True)
            if self.pk:
                qs = qs.exclude(pk= self.pk)
            if qs.count() >= limite:
                raise ValidationError(f"Solo se pueden habilitar {limite} fechas a la vez.")

    def __str__(self):
        estado = "Habilitada" if self.habilitada else "Deshabilatada"
        return f"{self.fecha} ({estado})"


class Reunion(models.Model):
    empresa = models.ForeignKey(EmpresaExportadora, on_delete=models.CASCADE)
    importador = models.ForeignKey(Importador, on_delete=models.CASCADE)
    fecha = models.DateField()
    horario = models.ForeignKey(HorarioDisponible, on_delete=models.CASCADE, default=1)
    mensaje = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=30, default='Programada')  # Programada, Cancelada, Realizada
    observaciones = models.TextField(blank=True)

    class Meta:
        unique_together = ('fecha', 'horario')

    def __str__(self):
        return f"Reunión entre {self.empresa} y {self.importador} el {self.fecha}"

class ConfiguracionSistema(models.Model):
    permitir_registro = models.BooleanField(default= True)
    permitir_login = models.BooleanField(default= True)

    def __str__(self):
        return "Configuracion del Sistema"