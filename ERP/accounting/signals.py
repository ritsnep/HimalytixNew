from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import JournalLine, Journal

@receiver(post_save, sender=JournalLine)
def update_journal_totals(sender, instance, **kwargs):
    """
    Updates the total_debit and total_credit of the parent Journal
    whenever a JournalLine is saved.
    """
    journal = instance.journal
    journal.update_totals()
    journal.save(update_fields=['total_debit', 'total_credit'])
