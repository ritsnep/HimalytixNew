class VoucherProcessError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def map_exception_to_error(exc: Exception) -> VoucherProcessError:
    text = str(exc).lower()
    if "insufficient stock" in text:
        return VoucherProcessError("INV-001", "Insufficient stock for requested item.")
    if "imbalanced" in text or "debit" in text and "credit" in text:
        return VoucherProcessError("GL-001", str(exc))
    if "period" in text and "open" in text:
        return VoucherProcessError("VCH-002", str(exc))
    return VoucherProcessError("VCH-500", str(exc))
