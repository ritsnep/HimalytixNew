# Inventory/api/import_export_views.py
"""
API Views for Excel Import/Export Operations
"""
import os
import tempfile
from pathlib import Path

from django.core.exceptions import ValidationError
from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiTypes

from utils.auth import get_user_organization
from utils.file_uploads import (
    ALLOWED_IMPORT_EXTENSIONS,
    MAX_IMPORT_UPLOAD_BYTES,
    iter_validated_files,
)

from ..utils.excel_import import (
    ProductImporter, PriceListImporter,
    InventoryAdjustmentImporter, BOMImporter
)
from ..utils.excel_export import (
    ProductExporter, PriceListExporter,
    InventoryExporter, BOMExporter
)
from ..models import PriceList, Warehouse
from enterprise.models import BillOfMaterial
from api.permissions import IsOrganizationMember

EXCEL_EXTENSIONS = {
    ext for ext in ALLOWED_IMPORT_EXTENSIONS if ext.startswith(".xl")
} or {".xlsx", ".xlsm"}


def _request_organization(request):
    organization = getattr(request, "organization", None) or get_user_organization(
        request.user
    )
    if not organization:
        raise ValidationError("Active organization required")
    return organization


def _prepare_import_file(uploaded_file, *, label: str):
    try:
        extracted = list(
            iter_validated_files(
                uploaded_file,
                allowed_extensions=EXCEL_EXTENSIONS,
                max_bytes=MAX_IMPORT_UPLOAD_BYTES,
                allow_archive=True,
                max_members=5,
                label=label,
            )
        )
    except ValidationError as exc:
        raise exc

    if not extracted:
        raise ValidationError("No workbook data found in upload")
    if len(extracted) > 1:
        raise ValidationError("Archives must contain exactly one workbook file")

    filename, content = extracted[0]
    content.seek(0)
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix)
    tmp_file.write(content.read())
    tmp_file.flush()
    tmp_file.close()
    return tmp_file.name


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Import Products",
    description="Import products from Excel file"
)
def import_products(request):
    """
    Import products from uploaded Excel file
    
    POST /api/inventory/import/products/
    Content-Type: multipart/form-data
    Body: file (Excel file)
    """
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        organization = _request_organization(request)
    except ValidationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        tmp_path = _prepare_import_file(
            request.FILES['file'], label='Product import file'
        )
        importer = ProductImporter(organization=organization, user_id=request.user.id)
        result = importer.import_from_file(tmp_path)
        return Response(result.to_dict(), status=status.HTTP_200_OK)
    except ValidationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Import Price List",
    description="Import price list items from Excel file"
)
def import_price_list(request):
    """
    Import price list items from uploaded Excel file
    
    POST /api/inventory/import/price-list/
    """
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        organization = _request_organization(request)
        tmp_path = _prepare_import_file(
            request.FILES['file'], label='Price list import file'
        )
        importer = PriceListImporter(organization=organization, user_id=request.user.id)
        result = importer.import_from_file(tmp_path)
        return Response(result.to_dict(), status=status.HTTP_200_OK)
    except ValidationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Import Inventory Adjustments",
    description="Import inventory adjustments from Excel file"
)
def import_inventory_adjustment(request):
    """
    Import inventory adjustments from uploaded Excel file
    
    POST /api/inventory/import/adjustments/
    Query params: adjustment_type (count|adjustment)
    """
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

    adjustment_type = request.query_params.get('adjustment_type', 'count')

    try:
        organization = _request_organization(request)
        tmp_path = _prepare_import_file(
            request.FILES['file'], label='Inventory adjustment file'
        )
        importer = InventoryAdjustmentImporter(
            organization=organization, user_id=request.user.id
        )
        result = importer.import_from_file(tmp_path, adjustment_type)
        return Response(result.to_dict(), status=status.HTTP_200_OK)
    except ValidationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Import Bill of Materials",
    description="Import BOM from Excel file"
)
def import_bom(request):
    """
    Import Bill of Materials from uploaded Excel file
    
    POST /api/inventory/import/bom/
    """
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        organization = _request_organization(request)
        tmp_path = _prepare_import_file(
            request.FILES['file'], label='BOM import file'
        )
        importer = BOMImporter(organization=organization, user_id=request.user.id)
        result = importer.import_from_file(tmp_path)
        return Response(result.to_dict(), status=status.HTTP_200_OK)
    except ValidationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)


# Export endpoints
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    summary="Download Product Import Template",
    description="Download blank Excel template for product import"
)
def export_product_template(request):
    """
    Download blank product import template
    
    GET /api/inventory/export/product-template/
    """
    try:
        file_buffer = ProductExporter.create_template()
        
        response = FileResponse(
            file_buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="product_import_template.xlsx"'
        return response
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    summary="Export Products",
    description="Export existing products to Excel file"
)
def export_products(request):
    """
    Export existing products to Excel
    
    GET /api/inventory/export/products/
    Query params: category_id (optional)
    """
    try:
        category_id = request.query_params.get('category_id')
        category = None
        
        if category_id:
            from ..models import ProductCategory
            category = ProductCategory.objects.get(
                id=category_id,
                organization=request.user.organization
            )
        
        file_buffer = ProductExporter.export_products(
            organization=request.user.organization,
            category=category
        )
        
        response = FileResponse(
            file_buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="products_export.xlsx"'
        return response
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    summary="Download Price List Template",
    description="Download blank Excel template for price list import"
)
def export_price_list_template(request):
    """
    Download blank price list import template
    
    GET /api/inventory/export/price-list-template/
    """
    try:
        file_buffer = PriceListExporter.create_template()
        
        response = FileResponse(
            file_buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="price_list_import_template.xlsx"'
        return response
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    summary="Export Price List",
    description="Export price list to Excel file"
)
def export_price_list(request, price_list_id):
    """
    Export price list to Excel
    
    GET /api/inventory/export/price-list/{id}/
    """
    try:
        price_list = PriceList.objects.get(
            id=price_list_id,
            organization=request.user.organization
        )
        
        file_buffer = PriceListExporter.export_price_list(price_list)
        
        response = FileResponse(
            file_buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"price_list_{price_list.code}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    except PriceList.DoesNotExist:
        return Response({'error': 'Price list not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    summary="Generate Physical Count Template",
    description="Generate Excel template with current inventory for physical count"
)
def export_inventory_count_template(request):
    """
    Generate physical count template with current inventory
    
    GET /api/inventory/export/count-template/
    Query params: warehouse_id (optional)
    """
    try:
        warehouse_id = request.query_params.get('warehouse_id')
        warehouse = None
        
        if warehouse_id:
            warehouse = Warehouse.objects.get(
                id=warehouse_id,
                organization=request.user.organization
            )
        
        file_buffer = InventoryExporter.create_count_template(
            organization=request.user.organization,
            warehouse=warehouse
        )
        
        response = FileResponse(
            file_buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"physical_count_{warehouse.code if warehouse else 'all'}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    summary="Export Stock Levels Report",
    description="Export current stock levels to Excel file"
)
def export_stock_report(request):
    """
    Export stock levels report
    
    GET /api/inventory/export/stock-report/
    Query params: warehouse_id (optional)
    """
    try:
        warehouse_id = request.query_params.get('warehouse_id')
        warehouse = None
        
        if warehouse_id:
            warehouse = Warehouse.objects.get(
                id=warehouse_id,
                organization=request.user.organization
            )
        
        file_buffer = InventoryExporter.export_stock_report(
            organization=request.user.organization,
            warehouse=warehouse
        )
        
        response = FileResponse(
            file_buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"stock_report_{warehouse.code if warehouse else 'all'}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    summary="Download BOM Template",
    description="Download blank Excel template for BOM import"
)
def export_bom_template(request):
    """
    Download blank BOM import template
    
    GET /api/inventory/export/bom-template/
    """
    try:
        file_buffer = BOMExporter.create_template()
        
        response = FileResponse(
            file_buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="bom_import_template.xlsx"'
        return response
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    summary="Export Bill of Materials",
    description="Export BOM to Excel file"
)
def export_bom(request, bom_id):
    """
    Export BOM to Excel
    
    GET /api/inventory/export/bom/{id}/
    """
    try:
        bom = BillOfMaterial.objects.get(
            id=bom_id,
            organization=request.user.organization
        )
        
        file_buffer = BOMExporter.export_bom(bom)
        
        response = FileResponse(
            file_buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"bom_{bom.product.code}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    except BillOfMaterial.DoesNotExist:
        return Response({'error': 'BOM not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
