from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models


class LocationNode(models.Model):
    class Type(models.TextChoices):
        COUNTRY = "COUNTRY", "Country"
        PROVINCE = "PROVINCE", "Province"
        DISTRICT = "DISTRICT", "District"
        LOCAL_LEVEL = "LOCAL_LEVEL", "Local level (Municipality/Gaupalika)"
        WARD = "WARD", "Ward"
        AREA = "AREA", "Area/Locality"

    id = models.CharField(primary_key=True, max_length=64)
    type = models.CharField(max_length=16, choices=Type.choices)

    name_en = models.CharField(max_length=128)
    name_np = models.CharField(max_length=128)

    code = models.CharField(max_length=32, blank=True, default="")
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.PROTECT,
    )

    is_active = models.BooleanField(default=True)

    # For fast fuzzy matching / dedupe:
    aliases_en = models.JSONField(default=list, blank=True)
    aliases_np = models.JSONField(default=list, blank=True)

    # Flexible attributes: local_level_category, ward_count, geo, postal_code, etc.
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["type", "is_active"]),
            models.Index(fields=["parent", "type", "is_active"]),
            models.Index(fields=["name_en"]),
        ]

    def clean(self) -> None:
        # Hard rules that match your plan:
        if self.type == self.Type.COUNTRY:
            if self.parent_id is not None:
                raise ValidationError("COUNTRY must not have a parent.")
        elif self.type == self.Type.PROVINCE:
            if not self.parent_id:
                raise ValidationError("PROVINCE must have a parent (COUNTRY).")
        elif self.type == self.Type.DISTRICT:
            if not self.parent_id:
                raise ValidationError("DISTRICT must have a parent (PROVINCE).")
        elif self.type == self.Type.LOCAL_LEVEL:
            if not self.parent_id:
                raise ValidationError("LOCAL_LEVEL must have a parent (DISTRICT).")

        # Parent-type enforcement (optional but recommended)
        if self.parent_id:
            expected_parent = {
                self.Type.PROVINCE: self.Type.COUNTRY,
                self.Type.DISTRICT: self.Type.PROVINCE,
                self.Type.LOCAL_LEVEL: self.Type.DISTRICT,
                self.Type.WARD: self.Type.LOCAL_LEVEL,
                self.Type.AREA: None,  # AREA can be under LOCAL_LEVEL or WARD depending on your design
            }.get(self.type)

            if expected_parent and self.parent and self.parent.type != expected_parent:
                raise ValidationError(f"{self.type} must have parent type {expected_parent}.")

            if self.type == self.Type.AREA and self.parent and self.parent.type not in (
                self.Type.LOCAL_LEVEL,
                self.Type.WARD,
            ):
                raise ValidationError("AREA must be under LOCAL_LEVEL or WARD.")

    def __str__(self) -> str:
        return f"{self.name_en} / {self.name_np} ({self.type})"


class ClusterTag(models.Model):
    class ScopeType(models.TextChoices):
        COMPANY = "COMPANY", "Company"
        BRANCH = "BRANCH", "Branch"
        DISTRICT = "DISTRICT", "District"
        LOCAL_LEVEL = "LOCAL_LEVEL", "Local level"

    id = models.CharField(primary_key=True, max_length=64)
    name_en = models.CharField(max_length=128)
    name_np = models.CharField(max_length=128)

    scope_type = models.CharField(max_length=16, choices=ScopeType.choices)
    scope_location = models.ForeignKey(
        LocationNode,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="scoped_cluster_tags",
        help_text="For LOCAL_LEVEL/DISTRICT scope. Leave null for COMPANY/BRANCH scope.",
    )

    is_active = models.BooleanField(default=True)
    meta = models.JSONField(default=dict, blank=True)

    members = models.ManyToManyField(
        LocationNode,
        through="ClusterTagMembership",
        related_name="cluster_tags",
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["scope_type", "is_active"]),
            models.Index(fields=["scope_location", "is_active"]),
        ]

    def clean(self) -> None:
        # If scope implies a location, enforce it.
        if self.scope_type in (self.ScopeType.DISTRICT, self.ScopeType.LOCAL_LEVEL):
            if not self.scope_location_id:
                raise ValidationError("scope_location is required for DISTRICT/LOCAL_LEVEL scope.")
        else:
            # COMPANY/BRANCH scope: keep it null to avoid confusion
            if self.scope_location_id:
                raise ValidationError("scope_location must be null for COMPANY/BRANCH scope.")

    def __str__(self) -> str:
        return f"{self.name_en} / {self.name_np}"


class ClusterTagMembership(models.Model):
    cluster = models.ForeignKey(ClusterTag, on_delete=models.CASCADE)
    node = models.ForeignKey(LocationNode, on_delete=models.CASCADE)

    # Optional: ordering/route metadata later
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("cluster", "node")]
        indexes = [
            models.Index(fields=["cluster", "node"]),
            models.Index(fields=["node"]),
        ]


class AddressRef(models.Model):
    """
    Reusable address reference enforcing: LOCAL_LEVEL mandatory, everything else optional.
    Attach this to customer/supplier/branch/etc via FK or OneToOne.
    """
    local_level = models.ForeignKey(
        LocationNode,
        on_delete=models.PROTECT,
        related_name="address_local_levels",
        limit_choices_to={"type": LocationNode.Type.LOCAL_LEVEL},
    )
    ward = models.ForeignKey(
        LocationNode,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="address_wards",
        limit_choices_to={"type": LocationNode.Type.WARD},
    )
    area = models.ForeignKey(
        LocationNode,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="address_areas",
        limit_choices_to={"type": LocationNode.Type.AREA},
    )

    # Cluster tags are optional, scoped per local level in your plan.
    cluster_tags = models.ManyToManyField(ClusterTag, blank=True, related_name="addresses")

    address_line1 = models.CharField(max_length=128, blank=True, default="")
    address_line2 = models.CharField(max_length=128, blank=True, default="")
    landmark = models.CharField(max_length=128, blank=True, default="")
    postal_code = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["local_level"]),
        ]

    def clean(self) -> None:
        if self.local_level and self.local_level.type != LocationNode.Type.LOCAL_LEVEL:
            raise ValidationError("local_level must be a LOCAL_LEVEL node.")
        if self.ward and self.ward.type != LocationNode.Type.WARD:
            raise ValidationError("ward must be a WARD node.")
        if self.area and self.area.type != LocationNode.Type.AREA:
            raise ValidationError("area must be an AREA node.")