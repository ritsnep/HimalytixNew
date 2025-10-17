'''
URL configuration for the new, standalone journal entry view.
'''
from django.urls import path
from .new_journal_entry_view import NewJournalEntryView

# It is good practice to namespace your app's URLs.
app_name = 'accounting_new'

urlpatterns = [
    path('new-entry/', NewJournalEntryView.as_view(), name='new_journal_entry_create'),
]
