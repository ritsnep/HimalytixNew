from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _

from utils.file_uploads import (
    ALLOWED_IMPORT_EXTENSIONS,
    MAX_IMPORT_UPLOAD_BYTES,
    iter_validated_files,
)


class JournalImportForm(forms.Form):
    file = forms.FileField(
        label=_('Spreadsheet File'),
        help_text=_('Upload an Excel, CSV, or ZIP archive containing a single workbook.'),
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data.get('file')
        if not uploaded_file:
            return uploaded_file

        allowed_extensions = ALLOWED_IMPORT_EXTENSIONS | {".csv", ".xls"}
        try:
            files = list(
                iter_validated_files(
                    uploaded_file,
                    allowed_extensions=allowed_extensions,
                    max_bytes=MAX_IMPORT_UPLOAD_BYTES,
                    allow_archive=True,
                    max_members=1,
                    label=str(_('Journal import file')),
                )
            )
        except DjangoValidationError as exc:
            raise forms.ValidationError(str(exc)) from exc

        if not files:
            raise forms.ValidationError(_('Uploaded file is empty.'))

        _, content = files[0]
        content.seek(0)
        return content