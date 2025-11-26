"""
Static file storage that appends the current APP_VERSION to asset URLs.
This naturally busts browser caches after a deploy or manual version bump.
"""
from django.contrib.staticfiles.storage import StaticFilesStorage

from utils.maintenance import get_effective_app_version


class VersionedStaticFilesStorage(StaticFilesStorage):
    """
    Append ?v=<APP_VERSION> to static asset URLs for natural cache-busting.

    Django's StaticFilesStorage.url signature does not accept "force" on 5.x,
    so we avoid passing through unknown kwargs.
    """

    def url(self, name, **kwargs):
        kwargs.pop("force", None)  # Keep compatibility with callers that send force.
        base_url = super().url(name) if not kwargs else super().url(name, **kwargs)
        version = get_effective_app_version()
        if version:
            separator = "&" if "?" in base_url else "?"
            return f"{base_url}{separator}v={version}"
        return base_url
