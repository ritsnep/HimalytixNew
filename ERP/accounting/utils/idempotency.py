import uuid


def resolve_idempotency_key(request, *, fallback: str | None = None) -> str:
    """
    Resolve an idempotency key from request headers or POST data.
    Generates a new UUID when none is provided.
    """
    header_key = request.headers.get("Idempotency-Key") or request.META.get("HTTP_IDEMPOTENCY_KEY")
    post_key = request.POST.get("idempotency_key") if hasattr(request, "POST") else None
    return header_key or post_key or fallback or str(uuid.uuid4())
