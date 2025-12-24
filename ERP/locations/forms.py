from django import forms
from .models import AddressRef, LocationNode


class AddressRefForm(forms.ModelForm):
    class Meta:
        model = AddressRef
        fields = [
            "local_level",
            "ward",
            "area",
            "cluster_tags",
            "address_line1",
            "address_line2",
            "landmark",
            "postal_code",
        ]

    local_level = forms.ModelChoiceField(
        queryset=LocationNode.objects.filter(type=LocationNode.Type.LOCAL_LEVEL, is_active=True),
        required=True,
        label="Municipality / Gaupalika (स्थानीय तह)",
    )
    ward = forms.ModelChoiceField(
        queryset=LocationNode.objects.filter(type=LocationNode.Type.WARD, is_active=True),
        required=False,
        label="Ward (वडा)",
    )
    area = forms.ModelChoiceField(
        queryset=LocationNode.objects.filter(type=LocationNode.Type.AREA, is_active=True),
        required=False,
        label="Area/Tole (टोल/क्षेत्र)",
    )