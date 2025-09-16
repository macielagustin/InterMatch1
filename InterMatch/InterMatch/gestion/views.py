from django.shortcuts import render, redirect, get_object_or_404
from .models import Usuario, Provincia, Localidad, Pais,  Rubro, Certificacion, Idioma, TipoProveedor, EmpresaExportadora, HorarioDisponible
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth import login 
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import ProtectedError
from .forms import UsuarioForm, EmpresaExportadoraForm, ImportadorForm, ReunionForm, FechaDisponibleForm, HorarioDisponibleForm, horarios_disponibles, CrearReunionForm, AdminReunionForm, PasswordResetRequestForm, SetPasswordForm, UsuarioAdminForm
from .models import Importador, Usuario, EmpresaCertificacion, Reunion , FechaDisponible, ConfiguracionSistema
from django.core.mail import send_mail, EmailMessage
from django.core import signing
from django.contrib.sites.shortcuts import get_current_site
import openpyxl
from .emails import enviar_correos_reunion_creada
from django.http import FileResponse, Http404
from django.utils.encoding import smart_str
from django.shortcuts import get_object_or_404
from .models import EmpresaExportadora


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

###################################################
###### RECUPERAR CONTRASEÑA #######################
###################################################

# Config de firma
RESET_SALT = "intermatch-password-reset"
RESET_MAX_AGE = 60 * 60 * 24  # 24 horas

def _build_reset_link(request, token):
    domain = get_current_site(request).domain
    protocol = 'https' if request.is_secure() else 'http'
    return f"{protocol}://{domain}/recuperar/{token}/"

def password_reset_request(request):
    """
    1) Usuario ingresa email o username.
    2) Si existe, se envía mail con link firmado con expiración.
    3) Siempre redirige a 'enviado' (no revela si existe o no).
    """
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            identificador = form.cleaned_data['identificador'].strip()
            usuario = Usuario.objects.filter(email__iexact=identificador).first()
            if not usuario:
                usuario = Usuario.objects.filter(username__iexact=identificador).first()

            # Genera y envía el mail solo si existe, pero no revelamos nada al usuario final
            if usuario:
                payload = {'uid': usuario.usuario_id, 'ts': timezone.now().timestamp()}
                token = signing.dumps(payload, salt=RESET_SALT)
                link = _build_reset_link(request, token)

                asunto = "Recuperación de contraseña - InterMatch"
                cuerpo = (
                    f"Hola {usuario.username},\n\n"
                    f"Recibimos una solicitud para restablecer tu contraseña.\n"
                    f"Hacé clic en el siguiente enlace (válido por 24 horas):\n\n{link}\n\n"
                    "Si no fuiste vos, ignorá este correo."
                )
                send_mail(
                    subject=asunto,
                    message=cuerpo,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER),
                    recipient_list=[usuario.email],
                    fail_silently=True,
                )

            return redirect('password_reset_done')
    else:
        form = PasswordResetRequestForm()

    return render(request, 'gestion/password_reset.html', {'form': form})

def password_reset_done(request):
    return render(request, 'gestion/password_reset_done.html')

def password_reset_confirm(request, token):
    """
    Valida el token firmado y no vencido.
    Si es válido, muestra formulario para setear nueva contraseña.
    """
    try:
        data = signing.loads(token, salt=RESET_SALT, max_age=RESET_MAX_AGE)
        uid = data.get('uid')
    except signing.BadSignature:
        messages.error(request, "El enlace no es válido o ha sido manipulado.")
        return redirect('password_reset_request')
    except signing.SignatureExpired:
        messages.error(request, "El enlace ha expirado. Solicitá uno nuevo.")
        return redirect('password_reset_request')

    usuario = get_object_or_404(Usuario, pk=uid)

    if request.method == 'POST':
        form = SetPasswordForm(request.POST)
        if form.is_valid():
            nueva = form.cleaned_data['password1']
            usuario.password = make_password(nueva)
            usuario.save()
            return redirect('password_reset_complete')
    else:
        form = SetPasswordForm()

    return render(request, 'gestion/password_reset_confirm.html', {'form': form})

def password_reset_complete(request):
    return render(request, 'gestion/password_reset_complete.html')

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
    # Si preferís sesión:
    # usuario_id = request.session.get('usuario_id')
    # if not usuario_id: return redirect('login')

    usuario = get_object_or_404(Usuario, pk=usuario_id)

    # (Opcional pero recomendado) Evitar 2 importadores para el mismo usuario
    if Importador.objects.filter(usuario=usuario).exists():
        messages.info(request, "Este usuario ya tiene un registro de Importador.")
        return redirect('login')  # o a su panel

    if request.method == 'POST':
        form = ImportadorForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    importador = form.save(commit=False)
                    importador.usuario = usuario  # ✅ asignar instancia
                    importador.save()
                    form.save_m2m()  # ✅ M2M luego del save()

                    # Actualizar rol
                    usuario.rol = 'Importador'
                    usuario.save(update_fields=['rol'])

                # Enviar correo
                enviar_correo_confirmacion_registro(
                    destinatario_email=usuario.email,
                    nombre_usuario=usuario.nombre,
                    tipo_usuario='Importador'
                )

                messages.success(request, "¡Importador registrado correctamente!")
                return redirect('registro_exitoso')

            except IntegrityError:
                messages.error(request, "Ocurrió un problema al guardar. Intentá nuevamente.")
        else:
            # Log de errores en consola y feedback en template
            print("errores en el formulario:", form.errors)
            messages.error(request, "Revisá los campos del formulario.")
    else:
        form = ImportadorForm()

    return render(request, 'gestion/registro_importador.html', {'form': form, 'usuario': usuario})



from django.http import JsonResponse
from .models import Provincia, Localidad

def provincias_por_pais_id(request, pais_id):
    qs = Provincia.objects.filter(pais_id=pais_id).order_by('nombre')
    data = list(qs.values('id', 'nombre'))
    return JsonResponse(data, safe=False)

def localidades_por_provincia_id(request, provincia_id):
    qs = Localidad.objects.filter(provincia_id=provincia_id).order_by('nombre')
    data = list(qs.values('id', 'nombre'))
    return JsonResponse(data, safe=False)

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
    user = request.user
    
    try:
        importador = Importador.objects.select_related('usuario').get(usuario=user)
    except Importador.DoesNotExist:
        return redirect('registro_importador', usuario_id=user.usuario_id)

    return render(request, 'gestion/panel_importador.html', {
        'importador': importador,
        'razon_social': importador.razon_social
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

def _clean_ids(raw_list):
    # quita vacíos/espacios y castea a int
    return [int(x) for x in raw_list if str(x).strip().isdigit()]

@login_required(login_url='login')
def editar_importador(request):
    usuario_id = request.session.get('usuario_id')
    user = get_object_or_404(Usuario, usuario_id=usuario_id)
    importador = get_object_or_404(Importador, usuario=user)

    if request.method == 'POST':
        importador.telefono = request.POST.get('telefono') or ""
        importador.sitio_web = request.POST.get('sitio_web') or ""
        importador.comentarios = request.POST.get('comentarios') or ""
        importador.cantidad_empleados = _to_int_or_none(request.POST.get('cantidad_empleados'))

        if request.FILES.get('logo'):
            importador.logo = request.FILES['logo']
        importador.save()

        # M2M
        rubros_ids  = _clean_ids(request.POST.getlist('rubros'))
        paises_ids  = _clean_ids(request.POST.getlist('paises_comercializa'))
        idiomas_ids = _clean_ids(request.POST.getlist('idiomas'))
        tipos_ids   = _clean_ids(request.POST.getlist('tipos_proveedor'))

        if rubros_ids is not None:
            importador.rubros.set(Rubro.objects.filter(pk__in=rubros_ids))
        if paises_ids is not None:
            importador.paises_comercializa.set(Pais.objects.filter(pk__in=paises_ids))
        if idiomas_ids is not None:
            importador.idiomas.set(Idioma.objects.filter(pk__in=idiomas_ids))
        if tipos_ids is not None:
            importador.tipos_proveedor.set(TipoProveedor.objects.filter(pk__in=tipos_ids))

        messages.success(request, "¡Perfil actualizado correctamente!")
        return redirect('perfil_importador')

    ctx = {
        'importador': importador,
        'rubros': Rubro.objects.all().order_by('nombre'),
        'paises': Pais.objects.all().order_by('nombre'),
        'idiomas': Idioma.objects.all().order_by('nombre'),
        'tipos_proveedor': TipoProveedor.objects.all().order_by('nombre'),
    }
    return render(request, 'gestion/editar_importador.html', ctx)

@login_required
def empresas_disponibles(request):
    empresas = EmpresaExportadora.objects.select_related('provincia', 'localidad').prefetch_related('rubro', 'certificaciones')
    return render (request, 'gestion/empresas_disponibles.html', {'empresas': empresas})

def descargar_brochure(request, empresa_id):
    empresa = get_object_or_404(EmpresaExportadora, pk=empresa_id)
    if not empresa.brochure:
        raise Http404("Sin brochure")
    f = empresa.brochure.open('rb')
    nombre = f"Brochure_{empresa.razon_social}.pdf"
    return FileResponse(f, as_attachment=True, filename=smart_str(nombre))

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

@login_required
def editar_usuario_admin(request, usuario_id):
    if not _require_admin(request):
        return redirect('login')

    usuario = get_object_or_404(Usuario, pk=usuario_id)  # si tu PK es usuario_id, Django igual lo mapea a pk
    if request.method == 'POST':
        form = UsuarioAdminForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario actualizado correctamente.")
            return redirect('lista_usuarios_admin')
        messages.error(request, "Revisá los datos del formulario.")
    else:
        form = UsuarioAdminForm(instance=usuario)

    return render(request, 'gestion/admin/editar_usuario.html', {
        'form': form,
        'obj': usuario,
    })

def _require_admin(request):
    if not request.user.is_authenticated or getattr(request.user, 'rol', '') != 'Administrador':
        messages.error(request, "No tenés permisos para esta acción.")
        return False
    return True

@login_required
def eliminar_usuario_admin(request, usuario_id):
    if not _require_admin(request):
        return redirect('login')

    if request.method != 'POST':
        messages.warning(request, "Método no permitido.")
        return redirect('lista_usuarios_admin')

    usuario = get_object_or_404(Usuario, pk=usuario_id)

    # Evitar que un admin se elimine a sí mismo (opcional pero recomendado)
    if getattr(request.user, 'pk', None) == usuario.pk:
        messages.error(request, "No podés eliminar tu propio usuario.")
        return redirect('lista_usuarios_admin')

    try:
        with transaction.atomic():
            usuario.delete()
        messages.success(request, "Usuario eliminado correctamente.")
    except ProtectedError:
        messages.error(request, "No se puede eliminar: tiene datos relacionados (empresa/importador/reuniones).")
    return redirect('lista_usuarios_admin')

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
    # Validación de rol admin (ajusta a tu modelo de usuario)
    if getattr(request.user, 'rol', None) != 'Administrador':
        return redirect('login')

    reunion = get_object_or_404(Reunion, id=reunion_id)

    if request.method == 'POST':
        form = AdminReunionForm(request.POST, instance=reunion)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()  # clean() ya valida disponibilidad; unique_together evita duplicado
                messages.success(request, "Reunión actualizada correctamente.")
                return redirect('gestionar_reuniones')
            except IntegrityError:
                messages.error(request, "Otro usuario tomó ese (fecha, horario) recién. Elegí otro.")
        else:
            messages.error(request, "Revisá los errores del formulario.")
    else:
        form = AdminReunionForm(instance=reunion)

    return render(request, 'gestion/editar_reunion.html', {'form': form, 'reunion': reunion})

@login_required(login_url='login')
def eliminar_reunion(request, reunion_id):
    if getattr(request.user, 'rol', None) != 'Administrador':
        return redirect('login')

    reunion = get_object_or_404(Reunion, id=reunion_id)

    if request.method == 'POST':
        reunion.delete()  # al borrar, el horario queda libre implícitamente
        from django.contrib import messages
        messages.info(request, "Reunión eliminada.")
        return redirect('gestionar_reuniones')

    return render(request, 'gestion/eliminar_reunion.html', {'reunion': reunion})

@login_required(login_url='login')
def toggle_habilitada(request, fecha_id):
    fecha = get_object_or_404(FechaDisponible, id=fecha_id)
    fecha.habilitada = not fecha.habilitada
    fecha.save(update_fields=['habilitada'])
    messages.success(request, f"Fecha {('habilitada' if fecha.habilitada else 'deshabilitada')}.")
    return redirect('gestionar_fechas')

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
    usuario = get_object_or_404(Usuario, usuario_id=request.session.get('usuario_id'))
    rol = request.session.get('rol')

    empresa = importador = None
    if rol == 'Importador' and tipo_receptor == 'empresa':
        importador = get_object_or_404(Importador, usuario=usuario)
        empresa = get_object_or_404(EmpresaExportadora, pk=receptor_id)
        nombre_receptor = str(empresa)
    elif rol == 'Empresa Exportadora' and tipo_receptor == 'importador':
        empresa = get_object_or_404(EmpresaExportadora, usuario=usuario)
        importador = get_object_or_404(Importador, pk=receptor_id)
        nombre_receptor = str(importador)
    else:
        messages.error(request, "No tenés permisos para crear esta reunión.")
        return redirect('inicio')

    # Traer fechas habilitadas
    fechas_hab = FechaDisponible.objects.filter(habilitada=True).order_by('fecha')
    if not fechas_hab.exists():
        messages.warning(request, "No hay fechas habilitadas por el administrador.")
        return redirect('panel_empresa' if rol == 'Empresa Exportadora' else 'panel_importador')  # o donde corresponda

    fecha_default_inst = fechas_hab.first()           # instancia
    fecha_default_date = fecha_default_inst.fecha     # date real

    if request.method == 'GET':
        # ⬅️ SETEAR INITIAL para que el select quede en la 1ª fecha y se carguen horarios
        form = CrearReunionForm(
            initial={'fecha': fecha_default_inst.pk},
            fecha_seleccionada=fecha_default_date
        )
        return render(request, 'gestion/crear_reunion.html', {
            'form': form,
            'nombre_receptor': nombre_receptor
        })

    # POST
    # ⬅️ REFRESH: no dependas de is_valid(); lee la fecha del POST y recalculá horarios
    if request.POST.get('refresh'):
        form = CrearReunionForm(request.POST)
        # Intentar obtener la fecha elegida del POST (id de FechaDisponible)
        fecha_pk = request.POST.get('fecha')
        fecha_sel_date = None
        if fecha_pk:
            try:
                fecha_sel_date = FechaDisponible.objects.get(pk=fecha_pk).fecha
            except FechaDisponible.DoesNotExist:
                pass
        form = CrearReunionForm(request.POST, fecha_seleccionada=fecha_sel_date or fecha_default_date)
        return render(request, 'gestion/crear_reunion.html', {
            'form': form,
            'nombre_receptor': nombre_receptor
        })

    # Confirmación final
    form = CrearReunionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revisá los campos.")
        return render(request, 'gestion/crear_reunion.html', {
            'form': form,
            'nombre_receptor': nombre_receptor
        })

    # fecha = instancia de FechaDisponible; necesitamos su .fecha (date)
    fecha_obj = form.cleaned_data['fecha'].fecha
    horario = form.cleaned_data['horario']
    mensaje = form.cleaned_data['mensaje'] or ""

    # Última verificación de disponibilidad
    if not horarios_disponibles(fecha_obj).filter(pk=horario.pk).exists():
        messages.error(request, "Ese horario se reservó recién. Elegí otro.")
        return redirect(request.path)

    try:
        with transaction.atomic():
            reunion = Reunion.objects.create(
                empresa=empresa,
                importador=importador,
                fecha=fecha_obj,     # DateField ✅
                horario=horario,
                mensaje=mensaje,
                estado='Programada',
                observaciones=""
            )
        transaction.on_commit(lambda: enviar_correos_reunion_creada(reunion))
        messages.success(request, f"¡Reunión programada para {fecha_obj} a las {horario.hora.strftime('%H:%M')}!")
        return redirect('panel_empresa' if rol == 'Empresa Exportadora' else 'panel_importador')
    except IntegrityError:
        messages.error(request, "Otro usuario tomó ese horario. Probá con otro.")
        return redirect(request.path)

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
