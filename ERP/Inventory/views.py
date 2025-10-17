from django.shortcuts import render

def dashboard(request):
    return render(request, 'inventory/dashboard.html')

def products(request):
    return render(request, 'inventory/products.html')

def categories(request):
    return render(request, 'inventory/categories.html')

def warehouses(request):
    return render(request, 'inventory/warehouses.html')

def stock_movements(request):
    return render(request, 'inventory/stock_movements.html')
