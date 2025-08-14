from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView
from .views import crear_reunion, panel_empresa_view


urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('registro/', views.registro, name='registro'),
    path('login/', views.login_view , name='login'),
    path('registro-persona/', views.registro_persona, name='registroPersona'),
    path("registro/", views.ir_a_registro, name="registro"), 
    
    path('registro_empresa/<int:usuario_id>/', views.registro_empresa, name='registro_empresa'),
    path('registro_importador/<int:usuario_id>/', views.registro_importador, name='registro_importador'),

    #PANEL EMPRESA #
    path('panel/empresa/', views.panel_empresa_view, name='panel_empresa'),
    path('empresa/ver-perfil/', views.ver_perfil_empresa, name='ver_perfil_empresa'),
    path('empresa/editar/', views.editar_empresa, name='editar_empresa'),
    path('empresa/importadores/', views.importadores_disponibles, name='importadores_disponibles'),
    path('empresa/importador/<int:importador_id>/', views.detalle_importador, name= 'detalle_importador'),

    # PANEL IMPORTADOR #
    path('panel/importador/', views.panel_importador_view, name='panel_importador'),
    path('importador/perfil/', views.perfil_importador, name='perfil_importador'),
    path('importador/editar/', views.editar_importador, name='editar_importador'),
    path('importador/empresas/', views.empresas_disponibles, name='empresas_disponibles'),
    path('importador/empresas/<int:empresa_id>/', views.detalle_empresa, name='detalle_empresa'),

    # PANEL ADMIN #
    path('panel-admin/', views.panel_admin, name='panel_admin'),
    path('panel/usuarios/', views.lista_usuarios_admin, name='lista_usuarios_admin'),
    path('admin/reuniones/', views.gestionar_reuniones, name='gestionar_reuniones'),
    path('panel-admin/reuniones/editar/<int:reunion_id>/', views.editar_reunion, name='editar_reunion'),
    path('panel-admin/reuniones/eliminar/<int:reunion_id>/', views.eliminar_reunion, name='eliminar_reunion'),
    path('panel_admin/reuniones/exportar/', views.exportar_reuniones_excel, name='exportar_reuniones_excel'),





    path('logout/', views.logout_view, name='cerrar_sesion'),


    path('api/provincias/', views.provincias_por_pais, name='provincias_por_pais'),
    path('api/localidades/', views.localidades_por_provincia, name='localidades_por_provincia'),

    
    #Registro empresa
    path('obtener_provincias/', views.obtener_provincias, name='obtener_provincias'),
    path('obtener_localidades/', views.obtener_localidades, name='obtener_localidades'),
    path('registro_exitoso/', views.registro_exitoso, name='registro_exitoso'),
    
    #Panel de Administrador
    path('panel_admin/', views.panel_admin, name='panel_admin'),
    path('gestionar_usuarios/', views.gestionar_usuarios, name='gestionar_usuarios'),
    path('gestionar_reuniones/', views.gestionar_reuniones, name='gestionar_reuniones'),
    path('definir_periodo/', views.definir_periodo, name='definir_periodo'),
    path('logout/', LogoutView.as_view(next_page='login'), name='cerrar_sesion'),
    path('definir_inscripcion/', views.definir_periodo, name='definir_inscripcion'),
    path('panel_admin/fechas/', views.gestionar_fechas, name= 'gestionar_fechas'),
    path('panel_admin/fechas/editar/<int:fecha_id>/', views.editar_fecha, name='editar_fecha'),
    path('panel_admin/eliminar/<int:fecha_id>/', views.eliminar_fecha, name='eliminar_fecha'),
    path('panel_admin/gestionar-horarios/', views.gestionar_horarios, name='gestionar_horarios'),
    path('panel_admin/editar-horario/<int:horario_id>/', views.editar_horario, name='editar_horario'),
    path('panel_admin/eliminar-horario/<int:horario_id>/', views.eliminar_horario, name='eliminar_horario'),

    #Reunion
    path('reunion/crear/<str:tipo_receptor>/<int:receptor_id>/', crear_reunion, name='crear_reunion'),
    path('reunion/confirmada/', views.reunion_exitosa, name='reunion_exitosa'),

]
