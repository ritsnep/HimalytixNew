from django.shortcuts import render

def profile(request):
    return render(request, 'account/profile.html')

def security(request):
    return render(request, 'account/security.html')

def billing(request):
    return render(request, 'account/billing.html')