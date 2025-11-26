from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Generator, Iterable, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.text import slugify

# Default limits/extensions can be overridden via Django settings
DEFAULT_ATTACHMENT_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".xlsm",
    ".csv",
    ".txt",
    ".json",
}
DEFAULT_IMPORT_EXTENSIONS = {".xlsx", ".xlsm"}

ALLOWED_ATTACHMENT_EXTENSIONS: set[str] = set(
    getattr(settings, "ATTACHMENT_ALLOWED_EXTENSIONS", DEFAULT_ATTACHMENT_EXTENSIONS)
)
ALLOWED_IMPORT_EXTENSIONS: set[str] = set(
    getattr(settings, "IMPORT_ALLOWED_EXTENSIONS", DEFAULT_IMPORT_EXTENSIONS)
)

MAX_ATTACHMENT_UPLOAD_BYTES: int = int(
    getattr(settings, "MAX_ATTACHMENT_SIZE_MB", 25) * 1024 * 1024
)
MAX_IMPORT_UPLOAD_BYTES: int = int(
    getattr(settings, "MAX_IMPORT_SIZE_MB", 15) * 1024 * 1024
)
MAX_ARCHIVE_MEMBERS: int = int(getattr(settings, "MAX_UPLOAD_ARCHIVE_MEMBERS", 25))


def _normalized_name(filename: str) -> str:
    """Return a filesystem-safe filename preserving the original suffix."""
    base = Path(filename or "upload").name
    suffix = Path(base).suffix.lower()
    stem = slugify(Path(base).stem) or "upload"
    return f"{stem}{suffix}" if suffix else stem


def _validate_extension(ext: str, allowed: Iterable[str]) -> None:
    if ext not in allowed:
        raise ValidationError(
            f"File type '{ext or 'unknown'}' is not allowed for this operation."
        )


def _validate_size(size: int | None, max_bytes: int, *, label: str) -> None:
    if size is None:
        return
    if size > max_bytes:
        raise ValidationError(
            f"{label} exceeds the maximum allowed size of {max_bytes // (1024 * 1024)} MB."
        )


def _read_file(uploaded_file) -> bytes:
    uploaded_file.seek(0)
    data = uploaded_file.read()
    uploaded_file.seek(0)
    return data


def iter_validated_files(
    uploaded_file,
    *,
    allowed_extensions: Iterable[str],
    max_bytes: int,
    allow_archive: bool = True,
    max_members: int | None = None,
    label: str = "File",
) -> Generator[Tuple[str, ContentFile], None, None]:
    """Yield sanitized ContentFile objects after validating size/extension.

    Supports optional ZIP archives; each member is validated individually and
    yielded as an independent file-like object for downstream processing.
    """

    max_members = max_members or MAX_ARCHIVE_MEMBERS
    ext = Path(getattr(uploaded_file, "name", "")).suffix.lower()
    _validate_size(getattr(uploaded_file, "size", None), max_bytes, label=label)

    if allow_archive and ext == ".zip":
        buffer = io.BytesIO(_read_file(uploaded_file))
        try:
            with zipfile.ZipFile(buffer) as archive:
                members = [info for info in archive.infolist() if not info.is_dir()]
                if not members:
                    raise ValidationError("Archive is empty.")
                if len(members) > max_members:
                    raise ValidationError(
                        f"Archives may include at most {max_members} files."
                    )
                for info in members:
                    _validate_size(info.file_size, max_bytes, label=label)
                    member_ext = Path(info.filename).suffix.lower()
                    _validate_extension(member_ext, allowed_extensions)
                    data = archive.read(info.filename)
                    content = ContentFile(data)
                    content.name = _normalized_name(info.filename)
                    content.seek(0)
                    yield content.name, content
        except zipfile.BadZipFile as exc:
            raise ValidationError("Uploaded ZIP could not be read.") from exc
    else:
        _validate_extension(ext, allowed_extensions)
        data = _read_file(uploaded_file)
        _validate_size(len(data), max_bytes, label=label)
        content = ContentFile(data)
        content.name = _normalized_name(getattr(uploaded_file, "name", "upload"))
        content.seek(0)
        yield content.name, content