from functools import wraps
from django.shortcuts import redirect
from .models import FechaDisponible, HorarioDisponible, Reunion

def usuario_logueado_requerido(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'usuario_id' not in request.session:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper

def get_fechas_habilitadas():
    return FechaDisponible.objects.filter(habilitada=True).order_by('fecha')

def get_horarios_disponibles(fecha_date):
    ocupados = (
        Reunion.objects
        .filter(fecha=fecha_date)
        .exclude(estado='Cancelada')
        .values_list('horario_id', flat=True)
    )
    return HorarioDisponible.objects.exclude(id__in=ocupados).order_by('hora')