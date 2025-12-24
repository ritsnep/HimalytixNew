from __future__ import annotations

from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import ClusterTag, LocationNode


def _q_param(request: HttpRequest, key: str, default: str = "") -> str:
    return (request.GET.get(key) or default).strip()


@require_GET
def api_location_children(request: HttpRequest) -> JsonResponse:
    """
    /api/locations/children?parent_id=...&type=DISTRICT&q=...
    """
    parent_id = _q_param(request, "parent_id")
    type_ = _q_param(request, "type")
    q = _q_param(request, "q")
    limit = int(_q_param(request, "limit", "50") or 50)

    qs = LocationNode.objects.filter(is_active=True)

    if type_:
        qs = qs.filter(type=type_)
    if parent_id:
        qs = qs.filter(parent_id=parent_id)
    else:
        # Allow fetching provinces by omitting parent_id and requesting PROVINCE
        pass

    if q:
        qs = qs.filter(
            Q(name_en__icontains=q)
            | Q(name_np__icontains=q)
            | Q(aliases_en__icontains=q)
            | Q(aliases_np__icontains=q)
        )

    items = list(
        qs.order_by("name_en")[:limit].values(
            "id", "type", "name_en", "name_np", "parent_id", "meta"
        )
    )
    return JsonResponse({"items": items})


@require_GET
def api_location_search(request: HttpRequest) -> JsonResponse:
    """
    /api/locations/search?q=...&types=LOCAL_LEVEL,AREA
    """
    q = _q_param(request, "q")
    types = [t.strip() for t in _q_param(request, "types", "LOCAL_LEVEL,AREA").split(",") if t.strip()]
    limit = int(_q_param(request, "limit", "50") or 50)

    if not q:
        return JsonResponse({"items": []})

    qs = LocationNode.objects.filter(is_active=True, type__in=types).filter(
        Q(name_en__icontains=q)
        | Q(name_np__icontains=q)
        | Q(aliases_en__icontains=q)
        | Q(aliases_np__icontains=q)
        | Q(code__icontains=q)
    )

    items = list(qs.order_by("type", "name_en")[:limit].values("id", "type", "name_en", "name_np", "parent_id", "meta"))
    return JsonResponse({"items": items})


@require_GET
def api_clusters(request: HttpRequest) -> JsonResponse:
    """
    /api/clusters?scope_type=LOCAL_LEVEL&scope_id=<local_level_id>&q=...
    """
    scope_type = _q_param(request, "scope_type", "LOCAL_LEVEL")
    scope_id = _q_param(request, "scope_id")
    q = _q_param(request, "q")
    limit = int(_q_param(request, "limit", "100") or 100)

    qs = ClusterTag.objects.filter(is_active=True, scope_type=scope_type)
    if scope_type in (ClusterTag.ScopeType.DISTRICT, ClusterTag.ScopeType.LOCAL_LEVEL):
        if scope_id:
            qs = qs.filter(scope_location_id=scope_id)
        else:
            return JsonResponse({"items": []})

    if q:
        qs = qs.filter(Q(name_en__icontains=q) | Q(name_np__icontains=q))

    items = list(qs.order_by("name_en")[:limit].values("id", "name_en", "name_np", "scope_type", "scope_location_id"))
    return JsonResponse({"items": items})


# -------------------
# HTMX partials
# -------------------

@require_GET
def htmx_location_picker(request: HttpRequest) -> HttpResponse:
    """
    Renders a reusable picker widget with:
    Province -> District -> Local Level (mandatory)
    + Area (optional)
    + Cluster tags (optional)
    """
    provinces = LocationNode.objects.filter(type=LocationNode.Type.PROVINCE, is_active=True).order_by("code", "name_en")
    return render(request, "locations/partials/location_picker.html", {"provinces": provinces})


@require_GET
def htmx_options_districts(request: HttpRequest) -> HttpResponse:
    province_id = _q_param(request, "province_id")
    districts = LocationNode.objects.filter(
        type=LocationNode.Type.DISTRICT,
        parent_id=province_id,
        is_active=True,
    ).order_by("name_en")
    return render(request, "locations/partials/options.html", {"items": districts})


@require_GET
def htmx_options_local_levels(request: HttpRequest) -> HttpResponse:
    district_id = _q_param(request, "district_id")
    local_levels = LocationNode.objects.filter(
        type=LocationNode.Type.LOCAL_LEVEL,
        parent_id=district_id,
        is_active=True,
    ).order_by("name_en")
    return render(request, "locations/partials/options.html", {"items": local_levels})


@require_GET
def htmx_options_areas(request: HttpRequest) -> HttpResponse:
    local_level_id = _q_param(request, "local_level_id")
    # AREA nodes are internal master data; parent could be LOCAL_LEVEL or WARD. This version uses LOCAL_LEVEL.
    areas = LocationNode.objects.filter(
        type=LocationNode.Type.AREA,
        parent_id=local_level_id,
        is_active=True,
    ).order_by("name_en")
    return render(request, "locations/partials/options.html", {"items": areas})


@require_GET
def htmx_cluster_tags(request: HttpRequest) -> HttpResponse:
    local_level_id = _q_param(request, "local_level_id")
    tags = ClusterTag.objects.filter(
        is_active=True,
        scope_type=ClusterTag.ScopeType.LOCAL_LEVEL,
        scope_location_id=local_level_id,
    ).order_by("name_en")
    return render(request, "locations/partials/cluster_tags.html", {"tags": tags})