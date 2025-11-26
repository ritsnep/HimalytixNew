import json
import random

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from accounting.models import Attachment, ChartOfAccount, Journal, JournalLine
from utils.file_uploads import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_UPLOAD_BYTES,
    iter_validated_files,
)

def new_journal_entry(request):
    """Render the journal entry page or handle the creation of a new journal entry."""
    if request.method == 'POST':
        data = request.POST
        
        # Basic journal data
        journal_description = data.get('description', 'Journal Entry')
        
        # Create Journal instance
        journal = Journal.objects.create(
            description=journal_description,
            status='draft',
            # user=request.user, # Uncomment if you have user authentication
        )

        line_indices = sorted(list(set([int(k.split('-')[1]) for k in data.keys() if k.startswith('lines-')])))

        for idx in line_indices:
            account_code = data.get(f'lines-{idx}-account')
            debit = data.get(f'lines-{idx}-debit')
            credit = data.get(f'lines-{idx}-credit')

            if not account_code and not debit and not credit:
                continue

            try:
                account = ChartOfAccount.objects.get(account_code=account_code)
                JournalLine.objects.create(
                    journal=journal,
                    account=account,
                    description=data.get(f'lines-{idx}-description'),
                    debit=float(debit) if debit else 0,
                    credit=float(credit) if credit else 0,
                    department=data.get(f'lines-{idx}-department'),
                    project=data.get(f'lines-{idx}-project'),
                )
            except ChartOfAccount.DoesNotExist:
                # Handle case where account does not exist
                # You might want to add an error message to the form
                pass
            except ValueError:
                # Handle case where debit/credit are not valid numbers
                pass
        
        # Redirect to the detail view of the newly created journal
        return redirect('accounting:journal_detail', pk=journal.pk)

    # For a GET request, render a blank journal entry page
    context = {
        'journal': None,
        'lines': [{'index': 1}], # Start with one empty line
        'pending_approvals_count': 0, # Or fetch real data
        'validation_error_count': 0,
    }
    return render(request, "accounting/journal_entry.html", context)


def add_journal_row(request):
    """HTMX endpoint to add a new blank journal line row."""
    # Get the index of the last row from the form data
    data = request.POST
    indices = [int(k.split('-')[1]) for k in data.keys() if k.startswith('lines-')]
    next_index = max(indices) + 1 if indices else 1
    
    # Render a new blank row
    context = {'index': next_index}
    return render(request, 'accounting/_journal_line_row.html', context)

def validate_journal_line(request):
    """HTMX endpoint to validate a single journal line input and update totals."""
    data = request.POST  # hx-post sends form fields in request.POST
    # Identify which line index was changed (from HX-Trigger-Name header if available)
    trigger = request.META.get('HTTP_HX_TRIGGER_NAME')  # e.g. "lines-2-account"
    changed_index = None
    changed_field = None
    if trigger:
        # e.g., trigger "lines-3-debit"
        try:
            prefix, field = trigger.rsplit('-', 1)
            # prefix like "lines-3", field like "debit"
            changed_index = int(prefix.split('-')[1])
            changed_field = field
        except Exception:
            pass

    # Parse all current lines from the form data
    # Each line has keys like lines-<i>-account, -debit, -credit, etc.
    line_indices = set()
    for key in data.keys():
        if key.startswith('lines-'):
            # key format "lines-{idx}-{field}"
            parts = key.split('-')
            if len(parts) >= 3:
                try:
                    line_indices.add(int(parts[1]))
                except ValueError:
                    continue

    # Calculate total debits and credits across all lines
    total_debit = 0.0
    total_credit = 0.0
    for idx in line_indices:
        # treat empty or invalid numbers as 0 for totals
        try:
            debit_val = float(data.get(f'lines-{idx}-debit', '') or 0)
            if debit_val > 0:
                total_debit += debit_val
        except ValueError:
            # invalid number input -> count as 0
            pass
        try:
            credit_val = float(data.get(f'lines-{idx}-credit', '') or 0)
            if credit_val > 0:
                total_credit += credit_val
        except ValueError:
            pass

    # Validate the specific changed field (or entire row if needed)
    error_msg = None
    total_errors = 0
    all_rows_html = ""

    for idx in sorted(list(line_indices)):
        account_code = data.get(f'lines-{idx}-account', '').strip()
        debit_str = data.get(f'lines-{idx}-debit', '').strip()
        credit_str = data.get(f'lines-{idx}-credit', '').strip()
        
        line_error = None
        if account_code and not ChartOfAccount.objects.filter(account_code=account_code).exists():
            line_error = "Invalid account"
            total_errors += 1
        
        try:
            if debit_str and float(debit_str) <= 0:
                line_error = "Must be > 0"
                total_errors += 1
        except ValueError:
            line_error = "Invalid number"
            total_errors += 1

        try:
            if credit_str and float(credit_str) <= 0:
                line_error = "Must be > 0"
                total_errors += 1
        except ValueError:
            line_error = "Invalid number"
            total_errors += 1

        line_context = {
            "index": idx,
            "line": {
                "account": account_code,
                "description": data.get(f'lines-{idx}-description', ''),
                "debit": debit_str,
                "credit": credit_str,
                "department": data.get(f'lines-{idx}-department', ''),
                "project": data.get(f'lines-{idx}-project', ''),
                "status": line_error if line_error else "—"
            }
        }
        # Re-render the specific row that was changed
        if idx == changed_index:
            row_html = render_to_string("accounting/_journal_line_row.html", line_context)
        else:
            row_html = ""
    
    # Render updated totals section as out-of-band swap
    imbalance = total_debit - total_credit
    balanced = abs(imbalance) < 0.005
    totals_context = {
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balanced": balanced,
        "imbalance": imbalance
    }
    totals_html = render_to_string("accounting/_totals_section.html", totals_context)

    # Render validation alert
    alert_html = ""
    if total_errors > 0:
        alert_html = render_to_string("accounting/_validation_alert.html", {'validation_error_count': total_errors})
    
    response_html = row_html + totals_html
    if alert_html:
        response_html += f'<div id="validation-alert-container" hx-swap-oob="true">{alert_html}</div>'
    else:
        response_html += '<div id="validation-alert-container" hx-swap-oob="true"></div>'

    return HttpResponse(response_html)

def auto_balance_entry(request):
    """HTMX endpoint to auto-balance the journal entry (add a balancing line if needed)."""
    data = request.POST
    # Sum current totals
    total_debit = total_credit = 0.0
    line_indices = set()
    for key, val in data.items():
        if key.startswith('lines-') and key.endswith('-debit'):
            idx = int(key.split('-')[1]); line_indices.add(idx)
            try:
                amt = float(val) if val else 0.0
            except ValueError:
                amt = 0.0
            if amt:
                total_debit += amt
        elif key.startswith('lines-') and key.endswith('-credit'):
            idx = int(key.split('-')[1]); line_indices.add(idx)
            try:
                amt = float(val) if val else 0.0
            except ValueError:
                amt = 0.0
            if amt:
                total_credit += amt
    imbalance = total_debit - total_credit
    response_html = ""
    if abs(imbalance) > 0.005:
        # Find first empty line (account not filled):contentReference[oaicite:5]{index=5}
        empty_idx = None
        for idx in sorted(line_indices):
            acct = data.get(f'lines-{idx}-account', '')
            desc = data.get(f'lines-{idx}-description', '')
            deb = data.get(f'lines-{idx}-debit', '')
            cred = data.get(f'lines-{idx}-credit', '')
            if acct.strip() == "" and (not deb and not cred):
                empty_idx = idx
                break
        new_line = False
        if empty_idx is None:
            # No empty line available, add a new one at next index:contentReference[oaicite:6]{index=6}
            empty_idx = (max(line_indices) + 1) if line_indices else 1
            new_line = True
        # Determine balancing amounts
        bal_debit = bal_credit = ""
        if imbalance > 0:
            # more debit than credit, need credit to balance
            bal_credit = f"{abs(imbalance):.2f}"
            bal_desc = "Auto-balancing entry"
            bal_debit = ""
        else:
            # more credit than debit, need debit to balance
            bal_debit = f"{abs(imbalance):.2f}"
            bal_desc = "Auto-balancing entry"
            bal_credit = ""
        # Prepare context for the balanced line
        line_context = {
            "index": empty_idx,
            "line": {
                "account": data.get(f'lines-{empty_idx}-account', ''),  # if reusing empty, keep whatever (likely empty)
                "description": bal_desc,
                "debit": bal_debit,
                "credit": bal_credit,
                "department": data.get(f'lines-{empty_idx}-department', ''),
                "project": data.get(f'lines-{empty_idx}-project', ''),
                "status": "—"
            }
        }
        new_row_html = render_to_string("accounting/_journal_line_row.html", line_context)
        if new_line:
            # Append the new row if we added one
            response_html += f'<tr hx-swap-oob="beforeend:#journal-grid-body">{new_row_html}</tr>'
        else:
            # Replace the existing empty row's content if re-used
            response_html += f'<tr id="line-{empty_idx}" hx-swap-oob="outerHTML">{new_row_html}</tr>'
        # Recalculate totals after balancing
        total_debit += float(bal_debit or 0.0)
        total_credit += float(bal_credit or 0.0)
        imbalance = total_debit - total_credit
    # Prepare out-of-band update for totals (same as in validate view)
    balanced = abs(imbalance) < 0.005
    totals_context = {
        "total_debit": f"{total_debit:.2f}",
        "total_credit": f"{total_credit:.2f}",
        "balanced": balanced,
        "imbalance": f"{abs(imbalance):.2f}"
    }
    totals_fragment = render_to_string("accounting/_totals_section.html", totals_context)
    response_html += totals_fragment
    return HttpResponse(response_html)

def journal_row_detail(request, line_index):
    """HTMX endpoint to load side-panel details for a given line."""
    data = request.GET  # hx-get sends data as query params
    idx = line_index
    account_code = data.get(f'lines-{idx}-account', '').strip()
    description = data.get(f'lines-{idx}-description', '').strip()
    
    account_name = "No account selected"
    account_type = "—"
    account_balance = "—"
    account_ytd = "—"

    if account_code:
        try:
            account = ChartOfAccount.objects.get(account_code=account_code)
            account_name = account.name
            account_type = account.get_account_type_display()
            # These would be calculated fields in a real application
            account_balance = f"${random.randint(1000, 20000):,.2f}"
            account_ytd = f"${random.randint(5000, 100000):,.2f}"
        except ChartOfAccount.DoesNotExist:
            account_name = "Unknown Account"
    else:
        account_code = "—"

    # Determine validation message for this line (reuse logic similar to validate_journal_line) 
    error_msg = None
    # Basic validation: format and numeric checks:contentReference[oaicite:7]{index=7}
    if account_code not in ("", "—") and account_code:  # account_code "—" means blank in UI
        if not (len(account_code) == 7 and account_code[4] == '-' and account_code[:4].isdigit() and account_code[5:].isdigit()):
            error_msg = "Error: Invalid account format"
    # Check debit/credit values
    debit_val = data.get(f'lines-{idx}-debit', '')
    credit_val = data.get(f'lines-{idx}-credit', '')
    if error_msg is None and debit_val:
        try:
            if float(debit_val) <= 0:
                error_msg = "Error: Must be positive"
        except ValueError:
            error_msg = "Error: Invalid number"
    if error_msg is None and credit_val:
        try:
            if float(credit_val) <= 0:
                error_msg = "Error: Must be positive"
        except ValueError:
            error_msg = "Error: Invalid number"

    # Simple AI insight based on description (similar to frontend logic):contentReference[oaicite:8]{index=8}
    insight_message = ""
    desc_lower = description.lower()
    if "supplies" in desc_lower:
        insight_message = "This appears to be a standard office supplies purchase. Consider allocating to the correct department if not already specified."
    elif "aws" in desc_lower or "amazon" in desc_lower:
        insight_message = "AWS cloud service charge detected. Based on past entries, this is likely a monthly recurring expense that should be accrued if not yet invoiced."
    else:
        insight_message = "No specific insights available for this entry."

    # (Attachments: for a new entry, none; if editing, you could fetch related attachments)
    attachments = []  # or fetch related attachments if applicable

    # Render the side panel detail partial
    context = {
        "account_name": account_name,
        "account_code": account_code,
        "account_type": account_type,
        "account_balance": account_balance,
        "account_ytd": account_ytd,
        "error_message": error_msg,
        "insight_message": insight_message,
        "attachments": attachments
    }
    detail_html = render_to_string("accounting/_side_panel_detail.html", context)
    return HttpResponse(detail_html)

def toggle_side_panel(request, state):
    """HTMX endpoint to toggle the side panel open or closed."""
    # state will be "open" or "close"
    open_panel = (state == "open")
    # Render the side panel div with appropriate classes and toggle button state
    # We preserve the inner content (if panel was open, request will not include it; we'll reset to empty state on reopen for simplicity)
    inner_content = render_to_string("accounting/_side_panel_detail.html", {}) if open_panel else ""
    # If reopening, show empty state prompt again (alternatively could remember last detail)
    if open_panel:
        inner_content = ('<div class="text-center py-10 text-gray-500">'
                         '<i class="fas fa-mouse-pointer text-gray-300 text-4xl mb-3"></i>'
                         '<p>Select a row to view details</p></div>')
    toggle_icon = '<i class="fas fa-chevron-right"></i>' if open_panel else '<i class="fas fa-chevron-left"></i>'
    toggle_url = reverse("accounting:journal_toggle_panel", args=["close" if open_panel else "open"])
    panel_html = (f'<div id="side-panel" class={"w-80" if open_panel else "w-0 overflow-hidden"} bg-white border-l border-gray-200 flex flex-col transition-all duration-300 ease-in-out hx-swap-oob="outerHTML">'
                  f'  <div class="border-b border-gray-200 px-4 py-3 flex items-center justify-between">'
                  f'    <h3 class="font-medium">Entry Details</h3>'
                  f'    <button type="button" hx-get="{toggle_url}" hx-target="#side-panel" hx-swap="outerHTML" class="text-gray-500 hover:text-gray-700">'
                  f'      {toggle_icon}'
                  f'    </button>'
                  f'  </div>'
                  f'  <div class="flex-1 overflow-auto p-4" id="side-panel-content">{inner_content}</div>'
                  f'</div>')
    return HttpResponse(panel_html)

def preview_ledger(request):
    """HTMX endpoint to generate the ledger impact preview modal."""
    data = request.POST
    # Build list of lines with numeric values
    lines = []
    # Determine all line indices present
    indices = set()
    for key in data.keys():
        if key.startswith('lines-') and '-' in key:
            try:
                indices.add(int(key.split('-')[1]))
            except:
                continue
    for idx in sorted(indices):
        acct = data.get(f'lines-{idx}-account', '').strip()
        desc = data.get(f'lines-{idx}-description', '').strip()
        # Parse amounts (empty string or invalid -> 0.0)
        try:
            debit = float(data.get(f'lines-{idx}-debit', '') or 0.0)
        except ValueError:
            debit = 0.0
        try:
            credit = float(data.get(f'lines-{idx}-credit', '') or 0.0)
        except ValueError:
            credit = 0.0
        # Only include lines that have a non-zero amount (skip completely blank lines)
        if (debit == 0.0 and credit == 0.0):
            continue
        # Determine impact text for this line
        # Derive broad account type via account code first digit:contentReference[oaicite:9]{index=9}
        try:
            account = ChartOfAccount.objects.get(account_code=acct)
            acct_type = account.get_account_type_display()
        except ChartOfAccount.DoesNotExist:
            acct_type = "Account"
        impact = ""
        if debit and debit > 0:
            # If it's an increase or decrease depends on account type (debit increases Assets/Expenses, decreases others)
            if acct_type in ["Asset", "Expense"]:
                impact = f"{acct_type} increase"
            else:
                impact = f"{acct_type} decrease"
        elif credit and credit > 0:
            if acct_type in ["Asset", "Expense"]:
                impact = f"{acct_type} decrease"
            else:
                impact = f"{acct_type} increase"
        else:
            impact = ""  # shouldn't happen if one side is always filled
        lines.append({
            "account": acct or "—",
            "description": desc or "(No description)",
            "debit": f"{debit:.2f}" if debit else "",
            "credit": f"{credit:.2f}" if credit else "",
            "impact": impact
        })
    # Render the ledger preview modal with these lines
    modal_html = render_to_string("accounting/_ledger_preview_modal.html", {"preview_lines": lines})
    return HttpResponse(modal_html)

def close_preview_modal(request):
    """HTMX endpoint to close the preview modal (clears it)."""
    # Returning an empty response will clear the targeted container
    return HttpResponse("")

def ai_suggest_entries(request):
    """HTMX endpoint for AI-based entry suggestions."""
    description = request.GET.get('description', '').lower()
    suggestions = []

    if 'aws' in description or 'amazon' in description:
        suggestions = [
            {'account': '6000-00', 'description': 'AWS Cloud Services', 'debit': '875.00', 'credit': ''},
            {'account': '2000-00', 'description': 'Accounts Payable - AWS', 'debit': '', 'credit': '875.00'}
        ]
    elif 'supplies' in description or 'office' in description:
        suggestions = [
            {'account': '5000-00', 'description': 'Office Supplies', 'debit': '350.00', 'credit': ''},
            {'account': '2000-00', 'description': 'Accounts Payable - Office Depot', 'debit': '', 'credit': '350.00'}
        ]
    
    return JsonResponse({'suggestions': suggestions})

def upload_attachment(request, journal_id):
    """HTMX endpoint to upload an attachment for a journal entry."""
    if request.method == 'POST':
        # In a real app, you would get the journal object
        # journal = Journal.objects.get(pk=journal_id)
        
        # For now, we'll just simulate the upload
        file = request.FILES.get('attachment')
        if file:
            try:
                validated_files = list(
                    iter_validated_files(
                        file,
                        allowed_extensions=ALLOWED_ATTACHMENT_EXTENSIONS,
                        max_bytes=MAX_ATTACHMENT_UPLOAD_BYTES,
                        allow_archive=True,
                        label="Attachment",
                    )
                )
            except ValidationError as exc:
                return HttpResponse(
                    f'<div class="list-group-item small text-danger">{exc}</div>',
                    status=400,
                )

            if not validated_files:
                return HttpResponse(
                    '<div class="list-group-item small text-danger">No files to upload.</div>',
                    status=400,
                )

            fragments = []
            for _, content in validated_files:
                # attachment = Attachment.objects.create(file=content, content_object=journal)
                fragments.append(
                    f'<div class="list-group-item small text-success">Successfully validated {content.name}</div>'
                )
            return HttpResponse(''.join(fragments))
    
    return HttpResponse('<div class="list-group-item small text-danger">Upload failed.</div>', status=400)

def post_journal(request, journal_id):
    """HTMX endpoint to post a journal entry using the central posting service."""
    try:
        journal = Journal.objects.get(pk=journal_id, organization=request.user.get_active_organization())
    except Journal.DoesNotExist:
        return HttpResponse('<span class="badge bg-danger-subtle text-danger-emphasis">Not Found</span>', status=404)

    if journal.status != 'draft':
        return HttpResponse('<div class="alert alert-warning">Only draft journals can be posted.</div>', status=400)

    try:
        from accounting.services.post_journal import post_journal as service_post_journal, JournalPostingError, JournalValidationError

        service_post_journal(journal, user=request.user)
        return HttpResponse(
            '<button class="btn btn-sm btn-success d-flex align-items-center gap-1" disabled>'
            '<i class="fas fa-check-circle"></i><span>Posted</span></button>'
        )
    except (JournalPostingError, JournalValidationError) as exc:
        return HttpResponse(f'<div class="alert alert-danger">{exc}</div>', status=400)
    except Exception:
        return HttpResponse('<div class="alert alert-danger">Unexpected error while posting.</div>', status=500)

def search_accounts(request):
    """HTMX endpoint to search for accounts."""
    query = request.GET.get('q', '').strip()
    index = request.GET.get('index', '1') # Default to index 1 if not provided
    
    if query:
        accounts = ChartOfAccount.objects.filter(account_name__icontains=query) | ChartOfAccount.objects.filter(account_code__icontains=query)
    else:
        accounts = ChartOfAccount.objects.all()[:10]

    context = {
        'accounts': accounts,
        'index': index
    }
    
    return render(request, 'accounting/_account_search_results.html', context)
