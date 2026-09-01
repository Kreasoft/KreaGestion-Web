from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from core.decorators import requiere_empresa
from empresas.middleware import resolver_sucursal_operativa

from .asistente import responder, snapshot_empresa


def _sucursal(request):
    return getattr(request, "sucursal_activa", None) or resolver_sucursal_operativa(request)


@login_required
@requiere_empresa
def resumen_dueno(request):
    """Resumen corto para el dueño: plata, deudas y lo que duele."""
    from django.shortcuts import redirect
    try:
        if request.user.perfil.tipo_usuario == 'cajero':
            return redirect('dashboard')
    except Exception:
        pass
    sucursal = _sucursal(request)
    snap = snapshot_empresa(request.empresa, sucursal)
    return render(request, "gestioncloud/resumen_dueno.html", {
        "snap": snap,
        "sucursal": sucursal,
    })


@login_required
@requiere_empresa
@require_POST
def asistente_preguntar(request):
    pregunta = (request.POST.get("pregunta") or request.POST.get("q") or "").strip()
    if not pregunta and request.content_type and "json" in (request.content_type or ""):
        import json
        try:
            pregunta = (json.loads(request.body.decode("utf-8") or "{}").get("pregunta") or "").strip()
        except (TypeError, ValueError):
            pregunta = ""
    data = responder(pregunta, request.empresa, _sucursal(request))
    return JsonResponse(data)
