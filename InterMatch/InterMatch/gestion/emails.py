# gestion/emails.py
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

def _get_emails_reunion(reunion):
    # ajustá si tus relaciones/atributos son distintos
    to_empresa = [getattr(reunion.empresa.usuario, 'email', None)]
    to_importador = [getattr(reunion.importador.usuario, 'email', None)]
    to_admin = [getattr(settings, 'EMAIL_ADMIN', None)]  # p.ej. en settings: EMAIL_ADMIN = "admin@tuapp.com"
    # filtrar None/vacíos
    return [e for e in to_empresa if e], [e for e in to_importador if e], [e for e in to_admin if e]

def enviar_correos_reunion_creada(reunion):
    asunto = f"Reunión confirmada: {reunion.fecha} {reunion.horario.hora.strftime('%H:%M')}"
    ctx = {
        "empresa": reunion.empresa,
        "importador": reunion.importador,
        "fecha": reunion.fecha,
        "hora": reunion.horario.hora.strftime('%H:%M'),
        "mensaje": reunion.mensaje or "-",
    }
    # templates HTML / texto (crearlos abajo)
    html_content = render_to_string("gestion/emails/reunion_confirmada.html", ctx)
    text_content = render_to_string("gestion/emails/reunion_confirmada.txt", ctx)

    de = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@intermatch.local")
    to_emp, to_imp, to_adm = _get_emails_reunion(reunion)

    # Enviar individuales (opción segura)
    for dests in (to_emp, to_imp, to_adm):
        if dests:
            msg = EmailMultiAlternatives(asunto, text_content, de, dests)
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)