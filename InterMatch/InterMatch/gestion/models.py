from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.conf import settings

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

class Provincia(models.Model):
    nombre = models.CharField(max_length=100)
    pais = models.ForeignKey(Pais, on_delete=models.CASCADE)

class Localidad(models.Model):
    nombre = models.CharField(max_length=100)
    provincia = models.ForeignKey(Provincia, on_delete=models.CASCADE)


class EmpresaPais(models.Model):
    empresa = models.ForeignKey('EmpresaExportadora', db_column='empresa_id', on_delete=models.CASCADE)
    pais = models.ForeignKey(Pais, on_delete=models.CASCADE)

    class Meta:
        db_table = 'empresaexportadora_paises_exporta'
        unique_together = ('empresa', 'pais')

    

class EmpresaExportadora(models.Model):
    empresa_id = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE)
    razon_social = models.CharField(max_length=100)
    cargo = models.CharField(max_length=50)
    rubro = models.ForeignKey(Rubro, on_delete=models.CASCADE)
    telefono = models.CharField(max_length=20)
    provincia = models.ForeignKey(Provincia, on_delete=models.CASCADE)
    localidad = models.ForeignKey(Localidad, on_delete=models.CASCADE)
    sitio_web = models.URLField(blank=True, null=True)
    brochure = models.FileField(upload_to='brochures/')
    logo = models.ImageField(upload_to='logos/')
    capacidad_productiva = models.IntegerField(db_column='capacidad_mensual')

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
    frecuencia_exportacion = models.CharField(max_length=20, choices=[
        ('Ocasional', 'Ocasional'),
        ('Frecuente', 'Frecuente'),
        ('Regular', 'Regular')
    ])
    comentarios = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'empresaexportadora'


class Importador(models.Model):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE)
    pais_origen = models.ForeignKey('Pais', on_delete=models.PROTECT)
    provincia = models.ForeignKey('Provincia', on_delete=models.PROTECT)
    localidad = models.ForeignKey('Localidad', on_delete=models.PROTECT)
    idiomas = models.ManyToManyField('Idioma')
    rubros = models.ManyToManyField('Rubro')
    paises_comercializa = models.ManyToManyField('Pais', related_name='importadores_que_comercializan')
    tipos_proveedor = models.ManyToManyField('TipoProveedor')


    razon_social = models.CharField(max_length=150)
    cargo = models.CharField(max_length=100)
    telefono = models.CharField(max_length=30)
    empleados = models.IntegerField()
    sitio_web = models.URLField()
    logo = models.ImageField(upload_to="logos_importador/", null=True, blank=True)

    tipo_importador = models.CharField(
        max_length=50,
        choices=[
            ('Distribuidor mayorista', 'Distribuidor mayorista'),
            ('Distribuidor minorista', 'Distribuidor minorista'),
            ('Retailer / Cadena comercial', 'Retailer / Cadena comercial'),
            ('Otro', 'Otro'),
        ]
    )
    tipo_importador_otro = models.CharField(max_length=100, blank=True, null=True)

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
        return self.razon_social

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

    def __str__(self):
        return str(self.fecha)


class Reunion(models.Model):
    empresa = models.ForeignKey(EmpresaExportadora, on_delete=models.CASCADE)
    importador = models.ForeignKey(Importador, on_delete=models.CASCADE)
    fecha = models.DateTimeField()
    horario = models.ForeignKey(HorarioDisponible, on_delete=models.CASCADE, default=1)
    mensaje = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=30, default='Programada')  # Programada, Cancelada, Realizada
    observaciones = models.TextField(blank=True)

    class Meta:
        unique_together = ('fecha', 'horario')

    def __str__(self):
        return f"Reunión entre {self.empresa} y {self.importador} el {self.fecha}"

