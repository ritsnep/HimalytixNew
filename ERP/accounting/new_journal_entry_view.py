'''
This file contains a new, standalone view for creating Journal Entries.
'''
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages

from .forms import JournalEntryForm, JournalEntryLineFormSet
from .models import JournalEntry

class NewJournalEntryView(View):
    """
    A new, standalone view for creating a standard Journal Entry.
    This view is built from scratch and does not inherit from other project views.
    """
    template_name = 'accounting/journal_entry.html'
    # A placeholder success URL, you should create a real success page
    # or redirect to the list/detail view of the created entry.
    success_url = '/' # Redirect to home page on success

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests.
        Displays a blank form for the Journal Entry and its lines.
        """
        form = JournalEntryForm()
        formset = JournalEntryLineFormSet(queryset=JournalEntry.objects.none())

        context = {
            'form': form,
            'formset': formset,
            'title': 'Create New Standard Journal Entry'
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests.
        Validates and saves the Journal Entry and its lines.
        """
        form = JournalEntryForm(request.POST)
        formset = JournalEntryLineFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            # Defer saving the main form until we have the lines associated
            journal_entry = form.save(commit=False)
            
            # Add user to the entry if they are authenticated
            if request.user.is_authenticated:
                journal_entry.user = request.user
            
            journal_entry.save()

            # Associate the lines with the newly created journal entry
            lines = formset.save(commit=False)
            for line in lines:
                line.journal_entry = journal_entry
                line.save()
            
            # Save the many-to-many relationships if any
            formset.save_m2m()

            messages.success(request, "Journal Entry created successfully.")
            return redirect(self.success_url)

        # If forms are not valid, re-render the page with the forms and their errors
        messages.error(request, "Please correct the errors below.")
        context = {
            'form': form,
            'formset': formset,
            'title': 'Create New Standard Journal Entry'
        }
        return render(request, self.template_name, context)
