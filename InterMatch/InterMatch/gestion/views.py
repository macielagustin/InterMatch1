from django.shortcuts import render, redirect, get_object_or_404
from .models import Usuario, Provincia, Localidad, Pais,  Rubro, Certificacion, Idioma, TipoProveedor, EmpresaExportadora, HorarioDisponible
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth import login 
from django.contrib.auth.hashers import check_password
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
from .forms import UsuarioForm, EmpresaExportadoraForm, ImportadorForm, ReunionForm, FechaDisponibleForm, HorarioDisponibleForm
from .models import Importador, Usuario, EmpresaCertificacion, Reunion , FechaDisponible, ConfiguracionSistema
from django.core.mail import send_mail, EmailMessage
import openpyxl


def inicio(request):
    return render(request, 'gestion/inicio.html')

def registro(request):
    usuario_id = request.session.get('usuario_id')

    return render(request, 'gestion/registro.html', {
        'usuario_id': usuario_id
    })

from django.shortcuts import render, redirect
from django.contrib.auth.hashers import check_password
from gestion.models import Usuario

def login_view(request):
    config = ConfiguracionSistema.objects.first()

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        try:
            user = Usuario.objects.get(username=username)

            # 🔐 Bloquear login solo para NO administradores si está desactivado
            if config and not config.permitir_login and user.rol != 'Administrador':
                return render(request, 'gestion/login_desactivado.html')

            if check_password(password, user.password):
                print("Login correcto")

                # Django login
                login(request, user)

                # Guardar info en sesión
                request.session['usuario_id'] = user.usuario_id
                request.session['rol'] = user.rol

                # Redirección por rol
                if user.rol == 'Administrador':
                    return redirect('panel_admin')
                elif user.rol == 'Empresa Exportadora':
                    try:
                        EmpresaExportadora.objects.get(usuario=user)
                        return redirect('panel_empresa')
                    except EmpresaExportadora.DoesNotExist:
                        return redirect('registro_empresa', usuario_id=user.usuario_id)
                elif user.rol == 'Importador':
                    from .models import Importador
                    try:
                        Importador.objects.get(usuario=user)
                        return redirect('panel_importador')
                    except Importador.DoesNotExist:
                        return redirect('registro_importador', usuario_id=user.usuario_id)
                else:
                    return redirect('inicio')
            else:
                return render(request, 'gestion/login.html', {'error': 'Usuario o contraseña incorrectos.'})
        
        except Usuario.DoesNotExist:
            return render(request, 'gestion/login.html', {'error': 'Usuario o contraseña incorrectos.'})

    return render(request, 'gestion/login.html')

def logout_view(request):
    request.session.flush()  # Elimina toda la sesión
    return redirect('login')  # Redirige al login o al inicio, según prefieras

#######################################################
############ REGISTROS ###############################
#####################################################

def enviar_correo_confirmacion_registro(destinatario_email, nombre_usuario, tipo_usuario):
    asunto = f"Confirmacion de Registro - InterMatch"
    mensaje = f"""
Hola {nombre_usuario},

Tu registro como {tipo_usuario} en InterMatch se ha completado exitosamente.

Ya puedes ingresar a tu panel para comenzar a usar la plataforma.

¡Gracias por unirte a Nosotros!

Atte: El equipo de InterMatch
"""
    remitente = settings.DEFAULT_FROM_EMAIL
    send_mail(asunto, mensaje, remitente, [destinatario_email])

def registro_persona(request):
    config = ConfiguracionSistema.objects.first()
    if config and not config.permitir_registro:
        return render (request, 'gestion/fuera_de_periodo.html')
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            usuario = form.save(commit=False)
            from django.contrib.auth.hashers import make_password
            usuario.password = make_password(usuario.password)
            usuario.fecha_registro = timezone.now().date()
            usuario.save()
            request.session['usuario_id'] = usuario.usuario_id
            return redirect('registro')
    else:
        form = UsuarioForm()

    return render(request, 'gestion/registroPersona.html', {'form': form})


def registro_empresa(request, usuario_id):
    usuario = get_object_or_404(Usuario, pk=usuario_id)

    if request.method == 'POST':
        form = EmpresaExportadoraForm(request.POST, request.FILES)
        if form.is_valid():
            empresa = form.save(commit=False)
            empresa.usuario = usuario
            empresa.save()
            form.save_m2m()  # para los campos normales M2M (como paises_exporta)


            usuario.rol = 'Empresa Exportadora'
            usuario.save()

            enviar_correo_confirmacion_registro(
                destinatario_email= usuario.email,
                nombre_usuario=usuario.nombre,
                tipo_usuario='Empresa Exportadora'
            )

            return redirect('registro_exitoso')
        else:
            print(form.errors)
    else:
        form = EmpresaExportadoraForm()

    context = {
        'form': form,
        'certificaciones': Certificacion.objects.all(),
        'paises': Pais.objects.all(),
        'rubros': Rubro.objects.all(),
        'provincias': Provincia.objects.all(),
        'localidades': Localidad.objects.all(),
        'usuario_id': usuario.usuario_id,
    }
    return render(request, 'gestion/registro_empresa.html', context)

def obtener_localidades(request):
    provincia_id = request.GET.get('provincia_id')

    if not provincia_id:
        return JsonResponse({'error': 'provincia_id no recibido'}, status=400)

    try:
        localidades = Localidad.objects.filter(provincia_id=provincia_id).values('id', 'nombre')
        return JsonResponse(list(localidades), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def obtener_provincias(request):
    pais_id = request.GET.get('pais_id')
    provincias = Provincia.objects.filter(pais_id=pais_id).values('id', 'nombre')
    return JsonResponse(list(provincias), safe=False)


def registro_exitoso(request):
    return render(request, 'gestion/registro_exitoso.html')


def ir_a_registro(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('registroPersona')

    return render(request, 'gestion/registro.html', {'usuario_id': usuario_id})


def registro_importador(request, usuario_id):
    usuario = get_object_or_404(Usuario, pk=usuario_id)

    if request.method == 'POST':
        form = ImportadorForm(request.POST, request.FILES)
        if form.is_valid():
            importador = form.save(commit=False)
            importador.usuario = usuario
            importador.save()
            form.save_m2m()  # Para idiomas, rubros, paises_comercializa, tipos_proveedor

            usuario.rol = 'Importador'
            usuario.save()

            enviar_correo_confirmacion_registro(
                destinatario_email= usuario.email,
                nombre_usuario=usuario.nombre,
                tipo_usuario='Importador'
            )

            return redirect('registro_exitoso')
        else:
            print("errores en el formulario:", form.errors)
    else:
        form = ImportadorForm()

    context = {
        'form': form,
        'paises': Pais.objects.all(),
        'provincias': Provincia.objects.all(),
        'localidades': Localidad.objects.all(),
        'usuario_id': usuario.usuario_id,
        'idiomas': Idioma.objects.all(),
        'rubros': Rubro.objects.all(),
        'tipos_proveedor': TipoProveedor.objects.all(),
    }
    return render(request, 'gestion/registro_importador.html', context)


from django.http import JsonResponse

def provincias_por_pais(request):
    pais_nombre = request.GET.get('pais')
    provincias = Provincia.objects.filter(pais__nombre__iexact=pais_nombre).values('nombre')
    return JsonResponse(list(provincias), safe=False)

def localidades_por_provincia(request):
    provincia_nombre = request.GET.get('provincia')
    localidades = Localidad.objects.filter(provincia__nombre__iexact=provincia_nombre).values('nombre')
    return JsonResponse(list(localidades), safe=False)

#                       #
#   PANEL DE EMPRESA    #
#                       #

@login_required(login_url='login')
def panel_empresa_view(request):
    try:
        empresa = (EmpresaExportadora.objects
                   .select_related('rubro', 'provincia', 'localidad')      # FKs
                   .prefetch_related('certificaciones', 'paises_exporta')  # M2M
                   .get(usuario=request.user))
    except EmpresaExportadora.DoesNotExist:
        return redirect('registro_empresa', usuario_id=request.user.id)

    return render(request, 'gestion/panel_empresa.html', {
        'empresa': empresa,
        'nombre_empresa': empresa.razon_social,  # por si lo usás en el H1
    })

@login_required
def ver_perfil_empresa(request):
    usuario_id = request.session.get('usuario_id')
    empresa = EmpresaExportadora.objects.get(usuario_id=usuario_id)
    return render(request, 'gestion/perfil_empresa.html', {'empresa': empresa})


@login_required
def editar_empresa(request):
    usuario_id = request.session.get('usuario_id')
    empresa = get_object_or_404(EmpresaExportadora, usuario_id=usuario_id)

    if request.method == 'POST':
        empresa.telefono = request.POST.get('telefono') or ""
        empresa.capacidad_productiva = request.POST.get('capacidad_productiva') or None
        empresa.sitio_web = request.POST.get('sitio_web') or ""
        empresa.comentarios = request.POST.get('comentarios') or ""

        # archivo (brochure)
        if 'brochure' in request.FILES and request.FILES['brochure']:
            empresa.brochure = request.FILES['brochure']

        empresa.save()
        return redirect('ver_perfil_empresa')

    return render(request, 'gestion/editar_empresa.html', {'empresa': empresa})

@login_required
def importadores_disponibles(request):
    importadores = Importador.objects.select_related('pais_origen', 'provincia', 'localidad').prefetch_related('rubros', 'idiomas', 'tipos_proveedor', 'paises_comercializa')
    return render(request, 'gestion/importadores_disponibles.html', {'importadores': importadores})

@login_required
def detalle_importador(request, importador_id):
    importador = get_object_or_404(
        Importador.objects.select_related('usuario', 'pais_origen', 'provincia', 'localidad')
        .prefetch_related('rubros', 'idiomas', 'tipos_proveedor', 'paises_comercializa'),
        pk=importador_id
    )
    return render(request, 'gestion/detalle_importador.html', {'importador': importador})


#                           #
#       PANEL IMPORTADOR    #
#                           #
@login_required(login_url='login')
def panel_importador_view(request):
    try:
        importador = Importador.objects.get(usuario=request.user)
        nombre_importador = importador.razon_social
    except Importador.DoesNotExist:
        return redirect('registro_importador', usuario_id=request.user.id)

    return render(request, 'gestion/panel_importador.html', {
        'razon_social': nombre_importador,
    })

@login_required
def perfil_importador(request):
    usuario_id = request.session.get('usuario_id')
    usuario = Usuario.objects.get(usuario_id=usuario_id)
    importador = Importador.objects.filter(usuario=usuario).first()

    if not importador:
        return redirect('registro_importador', usuario_id=usuario.id)

    return render(request, 'gestion/perfil_importador.html', {
        'importador': importador
    })

def _to_int_or_none(val):
    try:
        return int(val) if str(val).strip() != "" else None
    except (TypeError, ValueError):
        return None

@login_required
def editar_importador(request):
    # Usuario desde la sesión (tu esquema actual)
    usuario_id = request.session.get('usuario_id')
    usuario = get_object_or_404(Usuario, usuario_id=usuario_id)

    importador = Importador.objects.filter(usuario=usuario).first()
    if not importador:
        return redirect('registro_importador', usuario_id=usuario.id)

    if request.method == 'POST':
        # Campos simples
        importador.telefono = request.POST.get('telefono') or ""
        importador.sitio_web = request.POST.get('sitio_web') or ""
        importador.comentarios = request.POST.get('comentarios') or ""

        # Empleados (tu modelo usa 'cantidad_empleados'; si tenés 'empleados', ajustá aquí)
        cant = request.POST.get('cantidad_empleados')
        importador.cantidad_empleados = _to_int_or_none(cant)

        # Archivo
        if 'logo' in request.FILES and request.FILES['logo']:
            importador.logo = request.FILES['logo']

        importador.save()  # guardar antes de M2M

        # ManyToMany (asegurate que en el form los name= coincidan)
        rubros_ids = request.POST.getlist('rubros')
        paises_ids = request.POST.getlist('paises_comercializa')

        if rubros_ids is not None:
            importador.rubros.set(Rubro.objects.filter(id__in=rubros_ids))
        if paises_ids is not None:
            importador.paises_comercializa.set(Pais.objects.filter(id__in=paises_ids))

        messages.success(request, "¡Perfil actualizado correctamente!")
        return redirect('perfil_importador')

    # GET → solo los catálogos necesarios para los M2M que editás
    contexto = {
        'importador': importador,
        'rubros': Rubro.objects.all().order_by('nombre'),
        'paises': Pais.objects.all().order_by('nombre'),
    }
    return render(request, 'gestion/editar_importador.html', contexto)

@login_required
def empresas_disponibles(request):
    empresas = EmpresaExportadora.objects.select_related('provincia', 'localidad').prefetch_related('rubro', 'certificaciones')
    return render (request, 'gestion/empresas_disponibles.html', {'empresas': empresas})

@login_required
def detalle_empresa(request, empresa_id):
    empresa = get_object_or_404(
        EmpresaExportadora.objects.select_related(
            'usuario', 'provincia', 'localidad', 'rubro'
        ).prefetch_related(
            'certificaciones', 'paises_exporta'
        ),
        pk=empresa_id
    )
    return render(request, 'gestion/detalle_empresa.html', {
        'empresa': empresa
    })

####################################

######################################
#### PANEL ADMIN #####################
######################################
@login_required(login_url='login')
def panel_admin(request):
    print("ROL DEL USUARIO:", request.user.rol)

    if request.user.rol != 'Administrador':
        print("No es admin, redirigiendo a login")
        return redirect('login')

    return render(request, 'gestion/panel_admin.html')

@login_required
def lista_usuarios_admin(request):
    if request.user.rol != 'Administrador':
        return redirect ('login')
    
    rol_filtro = request.GET.get('rol')
    if rol_filtro:
        usuarios = Usuario.objects.filter(rol=rol_filtro)
    else:
        usuarios = Usuario.objects.all()

    return render(request, 'gestion/admin/lista_usuarios.html', {'usuarios': usuarios, 'rol_filtro': rol_filtro})

@login_required(login_url='login')
def gestionar_fechas(request):
    if request.method == 'POST':
        form = FechaDisponibleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('gestionar_fechas')
    else:
        form = FechaDisponibleForm()

    fechas = FechaDisponible.objects.all().order_by('fecha')

    return render(request, 'gestion/admin/gestionar_fechas.html', {
        'form': form,
        'fechas': fechas
    })

@login_required(login_url='login')
def editar_fecha(request, fecha_id):
    fecha = get_object_or_404(FechaDisponible, id=fecha_id)
    if request.method == 'POST':
        form = FechaDisponibleForm(request.POST, instance=fecha)
        if form.is_valid():
            form.save()
            return redirect('gestionar_fechas')
    else:
        form = FechaDisponibleForm(instance=fecha)
    return render(request, 'gestion/admin/editar_fecha.html', {'form': form})

@login_required(login_url='login')
def eliminar_fecha(request, fecha_id):
    fecha = get_object_or_404(FechaDisponible, id=fecha_id)
    if request.method == 'POST':
        fecha.delete()
        return redirect('gestionar_fechas')
    return render(request, 'gestion/admin/eliminar_fecha.html', {'fecha': fecha})

@login_required
def gestionar_horarios(request):
    horarios = HorarioDisponible.objects.all().order_by('hora')

    if request.method == 'POST':
        form = HorarioDisponibleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('gestionar_horarios')
    else:
        form = HorarioDisponibleForm()

    return render(request, 'gestion/gestionar_horarios.html', {
        'horarios': horarios,
        'form': form
    })

@login_required
def editar_horario(request, horario_id):
    horario = get_object_or_404(HorarioDisponible, id=horario_id)
    if request.method == 'POST':
        form = HorarioDisponibleForm(request.POST, instance=horario)
        if form.is_valid():
            form.save()
            return redirect('gestionar_horarios')
    else:
        form = HorarioDisponibleForm(instance=horario)
    return render(request, 'gestion/editar_horario.html', {'form': form, 'horario': horario})

@login_required
def eliminar_horario(request, horario_id):
    horario = get_object_or_404(HorarioDisponible, id=horario_id)
    if request.method == 'POST':
        horario.delete()
        return redirect('gestionar_horarios')
    return render(request, 'gestion/eliminar_horario.html', {'horario': horario})

@login_required(login_url='login')
def gestionar_reuniones(request):
    if request.user.rol != 'Administrador':
        return redirect('login')

    reuniones = Reunion.objects.select_related('empresa__usuario', 'importador__usuario').order_by('-fecha')

    return render(request, 'gestion/gestionar_reuniones.html', {
        'reuniones': reuniones
    })

@login_required(login_url='login')
def editar_reunion(request, reunion_id):
    if request.user.rol != 'Administrador':
        return redirect('login')

    reunion = get_object_or_404(Reunion, id=reunion_id)

    if request.method == 'POST':
        form = ReunionForm(request.POST, instance=reunion)
        if form.is_valid():
            form.save()
            return redirect('gestionar_reuniones')
    else:
        form = ReunionForm(instance=reunion)

    return render(request, 'gestion/editar_reunion.html', {'form': form, 'reunion': reunion})

@login_required(login_url='login')
def eliminar_reunion(request, reunion_id):
    if request.user.rol != 'Administrador':
        return redirect('login')

    reunion = get_object_or_404(Reunion, id=reunion_id)

    if request.method == 'POST':
        reunion.delete()
        return redirect('gestionar_reuniones')

    return render(request, 'gestion/eliminar_reunion.html', {'reunion': reunion})

@login_required(login_url='login')
def exportar_reuniones_excel(request):
    if request.session.get('rol') != 'Administrador':
        return redirect('login')

    # Crear el libro y la hoja
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reuniones"

    # Encabezados
    ws.append([
        "Empresa",
        "Importador",
        "Fecha",
        "Horario",
        "Estado",
        "Mensaje"
    ])

    # Agregar datos
    reuniones = Reunion.objects.select_related('empresa', 'importador').all()

    for r in reuniones:
        ws.append([
            r.empresa.razon_social,
            r.importador.razon_social,
            r.fecha.strftime("%d/%m/%Y"),
            r.horario.hora.strftime("%H:%M"),
            r.estado,
            r.mensaje or ""
        ])

    # Preparar respuesta HTTP
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = 'attachment; filename=reuniones.xlsx'
    wb.save(response)
    return response

def configuracion_sistema_view(request):
    if request.session.get('rol') != 'Administrador':
        return redirect('login')

    config = ConfiguracionSistema.objects.first()
    mensaje = None

    if request.method == 'POST':
        permitir_registro = bool(request.POST.get('permitir_registro'))
        permitir_login = bool(request.POST.get('permitir_login'))

        if config:
            config.permitir_registro = permitir_registro
            config.permitir_login = permitir_login
            config.save()
            mensaje = "Configuración actualizada correctamente."
        else:
            ConfiguracionSistema.objects.create(
                permitir_registro=permitir_registro,
                permitir_login=permitir_login
            )
            mensaje = "Configuración creada correctamente."

    return render(request, 'gestion/configuracion_sistema.html', {
        'config': config,
        'mensaje': mensaje
    })

def difusion_admin_view(request):
    if request.session.get('rol') != 'Administrador':
        return redirect('login')

    mensaje_enviado = False

    if request.method == 'POST':
        asunto = request.POST.get('asunto')
        cuerpo = request.POST.get('mensaje')
        destinatario = request.POST.get('destinatario')

        # Filtrar destinatarios según lo elegido
        if destinatario == 'Empresas':
            usuarios = Usuario.objects.filter(rol='Empresa Exportadora')
        elif destinatario == 'Importadores':
            usuarios = Usuario.objects.filter(rol='Importador')
        else:
            usuarios = Usuario.objects.exclude(rol='Administrador')  # Todos menos admin

        emails = [u.email for u in usuarios]

        # Enviar solo si hay emails válidos
        if emails:
            email = EmailMessage(
                subject=asunto,
                body=cuerpo,
                from_email='andriuolo27@gmail.com',
                to=['difusion@intermatch.com'],
                bcc=emails
            )
            email.send(fail_silently=False)

    return render(request, 'gestion/admin/difusion_admin.html', {
        'mensaje_enviado': mensaje_enviado
    })



######################################
######## REUNION #####################
######################################

@login_required(login_url='login')
def crear_reunion(request, tipo_receptor, receptor_id):
    usuario_id = request.session.get('usuario_id')
    rol = request.session.get('rol')

    if not usuario_id or not rol:
        return redirect('login')

    usuario = get_object_or_404(Usuario, usuario_id=usuario_id)
    fecha_reunion = timezone.now().date()  # ✅ Ahora está disponible en todo el scope

    # Inicializar variables
    reunion = None
    empresa = None
    importador = None

    if rol == 'Importador' and tipo_receptor == 'empresa':
        importador = get_object_or_404(Importador, usuario=usuario)
        empresa = get_object_or_404(EmpresaExportadora, empresa_id=receptor_id)
        reunion = Reunion(importador=importador, empresa=empresa)

    elif rol == 'Empresa Exportadora' and tipo_receptor == 'importador':
        empresa = get_object_or_404(EmpresaExportadora, usuario=usuario)
        importador = get_object_or_404(Importador, id=receptor_id)
        reunion = Reunion(importador=importador, empresa=empresa)
    else:
        return redirect('login')  # Seguridad extra

    if request.method == 'POST':
        form = ReunionForm(request.POST, instance=reunion)
        if form.is_valid():
            nueva_reunion = form.save(commit=False)
            nueva_reunion.fecha = fecha_reunion  # ⏰ Fecha fija configurada
            nueva_reunion.save()
            form.save_m2m()

            from django.core.mail import send_mail
            from django.conf import settings

            asunto = 'Confirmacion de Reunion - InterMatch'
            mensaje = f'''
        Hola!

        Se ha confirmado la reunion entre:
        Empresa: {empresa.razon_social}
        Importador: {importador.razon_social}
        Fecha: {nueva_reunion.fecha.strftime('%d/%m/%Y')}
        Horario: {nueva_reunion.horario.hora.strftime('%H:%M')}
        Mensaje: {nueva_reunion.mensaje or "Sin Mensaje"}

        Gracias por utilizar InterMatch.
                '''
            
            destinatarios = [
                empresa.usuario.email,
                importador.usuario.email,
                'andriuolo27@gmail.com'
            ]
            
            send_mail(
                    asunto,
                    mensaje,
                    settings.DEFAULT_FROM_EMAIL,
                    destinatarios,
                    fail_silently=False,
            )

            return redirect('reunion_exitosa')
        else:
            print("❌ Errores en el formulario:", form.errors)
    else:
        horarios_ocupados = Reunion.objects.filter(
            fecha=fecha_reunion
        ).values_list('horario_id', flat=True)

        horarios_disponibles = HorarioDisponible.objects.exclude(id__in=horarios_ocupados)

        form = ReunionForm(instance=reunion)
        form.fields['horario'].queryset = horarios_disponibles

    nombre_receptor = empresa.razon_social if tipo_receptor == 'empresa' else importador.razon_social

    return render(request, 'gestion/crear_reunion.html', {
        'form': form,
        'tipo_receptor': tipo_receptor,
        'nombre_receptor': nombre_receptor,
    })

def reunion_exitosa(request):
    return render(request, 'gestion/reunion_exitosa.html')

def enviar_correo_prueba(request):
    send_mail(
        subject='prueba de correo desde intermatch',
        message='esto es un mensaje de prueba',
        from_email= None,
        recipient_list=['andriuolo27@gmail.com'],
        fail_silently=False,
    )
    return HttpResponse("Correo Enviado!")




def gestionar_usuarios(request):
    return render(request, 'gestion/gestionar_usuarios.html')


def definir_periodo(request):
    return render(request, 'gestion/definir_periodo.html')

def registroPersona(request):
    return render(request, 'gestion/registroPersona.html')
