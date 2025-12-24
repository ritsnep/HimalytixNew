from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html

from .models import AddressRef, ClusterTag, ClusterTagMembership, LocationNode


class ClusterTagMembershipInline(admin.TabularInline):
    model = ClusterTagMembership
    extra = 0
    autocomplete_fields = ["node"]


@admin.register(LocationNode)
class LocationNodeAdmin(admin.ModelAdmin):
    list_display = ["id", "name_en", "name_np", "type", "parent", "is_active"]
    list_filter = ["type", "is_active", ("parent", admin.RelatedOnlyFieldListFilter)]
    search_fields = ["name_en", "name_np", "code", "aliases_en", "aliases_np"]
    readonly_fields = ["id"]
    ordering = ["type", "name_en"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("parent")

    def parent_type(self, obj):
        return obj.parent.type if obj.parent else None

    parent_type.short_description = "Parent Type"


@admin.register(ClusterTag)
class ClusterTagAdmin(admin.ModelAdmin):
    list_display = ["id", "name_en", "name_np", "scope_type", "scope_location", "is_active"]
    list_filter = ["scope_type", "is_active", ("scope_location", admin.RelatedOnlyFieldListFilter)]
    search_fields = ["name_en", "name_np"]
    readonly_fields = ["id"]
    ordering = ["scope_type", "name_en"]
    inlines = [ClusterTagMembershipInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("scope_location")


@admin.register(ClusterTagMembership)
class ClusterTagMembershipAdmin(admin.ModelAdmin):
    list_display = ["cluster", "node"]
    list_filter = [("cluster", admin.RelatedOnlyFieldListFilter), ("node", admin.RelatedOnlyFieldListFilter)]
    search_fields = ["cluster__name_en", "cluster__name_np", "node__name_en", "node__name_np"]
    autocomplete_fields = ["cluster", "node"]
    ordering = ["cluster", "node"]


@admin.register(AddressRef)
class AddressRefAdmin(admin.ModelAdmin):
    list_display = ["id", "local_level", "ward", "area", "address_line1"]
    list_filter = [("local_level", admin.RelatedOnlyFieldListFilter)]
    search_fields = ["local_level__name_en", "local_level__name_np", "address_line1", "address_line2", "landmark"]
    autocomplete_fields = ["local_level", "ward", "area"]
    ordering = ["local_level", "address_line1"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("local_level", "ward", "area")

    def cluster_tags_count(self, obj):
        return obj.cluster_tags.count()

    cluster_tags_count.short_description = "Cluster Tags"