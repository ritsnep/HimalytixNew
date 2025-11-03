# accounting/views/journal_entry.py
# Drop-in minimal Django views to render the new Journal Entry page
# and accept JSON payloads for save/submit/approve.
#
# Replace with your real persistence logic as needed.

from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import json

def journal_entry(request):
  """Render the Excel-like Journal Entry UI template."""
  return render(request, "accounting/journal_entry.html")

def _read_json(request):
  try:
    return json.loads(request.body.decode("utf-8") or "{}")
  except Exception:
    return {}

@csrf_exempt  # Remove if you pass CSRF token correctly from the front-end
def journal_save_draft(request):
  if request.method != "POST":
    return HttpResponseNotAllowed(["POST"])
  payload = _read_json(request)
  # TODO: persist `payload` into your models as a Draft
  # e.g., Journal + JournalLine with status="Draft"
  return JsonResponse({"ok": True, "status": "draft_saved"})

@csrf_exempt
def journal_submit(request):
  if request.method != "POST":
    return HttpResponseNotAllowed(["POST"])
  payload = _read_json(request)
  # TODO: validate and persist with status="Submitted"
  return JsonResponse({"ok": True, "status": "submitted"})

@csrf_exempt
def journal_approve(request):
  if request.method != "POST":
    return HttpResponseNotAllowed(["POST"])
  payload = _read_json(request)
  # TODO: business rules; status="Approved"
  return JsonResponse({"ok": True, "status": "approved"})
