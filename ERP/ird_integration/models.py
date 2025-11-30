import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models
from django.utils import timezone


class EncryptedCharField(models.CharField):
    def __init__(self, *args, encryption_key: str | None = None, **kwargs):
        self._encryption_key = encryption_key
        self._fernet: Fernet | None = None
        super().__init__(*args, **kwargs)

    def _ensure_fernet(self) -> Fernet:
        if self._fernet is None:
            raw_key = self._encryption_key or getattr(settings, "IRD_ENCRYPTION_KEY", settings.SECRET_KEY)
            digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
            secret = base64.urlsafe_b64encode(digest)
            self._fernet = Fernet(secret)
        return self._fernet

    def _encrypt(self, value: str) -> str:
        return self._ensure_fernet().encrypt(value.encode("utf-8")).decode("ascii")

    def _decrypt(self, value: str | None) -> str | None:
        if not value:
            return value
        try:
            return self._ensure_fernet().decrypt(value.encode("ascii")).decode("utf-8")
        except Exception:
            return value

    def from_db_value(self, value, expression, connection):
        return self._decrypt(value)

    def to_python(self, value):
        return self._decrypt(value)

    def get_prep_value(self, value):
        raw = super().get_prep_value(value)
        if raw in (None, ""):
            return raw
        return self._encrypt(str(raw))


class IRDSettings(models.Model):
    seller_pan = models.CharField("Seller PAN", max_length=20)
    username = models.CharField("IRD Username", max_length=100)
    password = EncryptedCharField("IRD Password", max_length=100)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "IRD Settings"
        verbose_name_plural = "IRD Settings"

    def __str__(self) -> str:
        return f"IRD Settings (PAN: {self.seller_pan})"


class Invoice(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField()
    fiscal_year = models.CharField(max_length=20)
    buyer_pan = models.CharField(max_length=20)
    buyer_name = models.CharField(max_length=200)

    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_sales_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    excisable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    excise = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_sales_hst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_for_esf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    esf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    export_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_exempted_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"

    def __str__(self) -> str:
        return f"Invoice {self.invoice_number} ({self.invoice_date.isoformat()})"


class CreditNote(models.Model):
    credit_note_number = models.CharField(max_length=50, unique=True)
    credit_note_date = models.DateField()
    fiscal_year = models.CharField(max_length=20)
    reason_for_return = models.CharField(max_length=255)
    ref_invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="credit_notes")
    buyer_pan = models.CharField(max_length=20)
    buyer_name = models.CharField(max_length=200)

    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_sales_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    excisable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    excise = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_sales_hst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_for_esf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    esf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    export_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_exempted_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(
        max_length=10,
        choices=Invoice.STATUS_CHOICES,
        default=Invoice.STATUS_PENDING,
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Credit Note"
        verbose_name_plural = "Credit Notes"

    def __str__(self) -> str:
        return f"Credit Note {self.credit_note_number} ({self.credit_note_date.isoformat()})"


class IRDLog(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ird_logs",
    )
    credit_note = models.ForeignKey(
        CreditNote,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ird_logs",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    request_payload = models.TextField()
    response_payload = models.TextField()
    success = models.BooleanField(default=False)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "IRD API Log"
        verbose_name_plural = "IRD API Logs"

    def __str__(self) -> str:
        target = self.invoice or self.credit_note
        if target:
            label = "Invoice" if self.invoice else "Credit Note"
            return f"IRDLog for {label} {target}"
        return "IRDLog (no target)"
