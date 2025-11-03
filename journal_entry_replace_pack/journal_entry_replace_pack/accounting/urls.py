# accounting/urls.py
from django.urls import path
from .views import journal_entry as je

app_name = "accounting"

urlpatterns = [
    path("journal-entry/", je.journal_entry, name="journal_entry"),
    path("journal-entry/save-draft/", je.journal_save_draft, name="journal_save_draft"),
    path("journal-entry/submit/", je.journal_submit, name="journal_submit"),
    path("journal-entry/approve/", je.journal_approve, name="journal_approve"),
]
