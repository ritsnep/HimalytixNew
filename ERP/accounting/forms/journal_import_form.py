from django import forms
from django.core.validators import FileExtensionValidator

from django.utils.translation import gettext_lazy as _

class JournalImportForm(forms.Form):
    file = forms.FileField(
        label=_('Spreadsheet File'),
        help_text=_('Upload a CSV or Excel file.'),
        validators=[FileExtensionValidator(allowed_extensions=['csv', 'xlsx', 'xls'])]
    )