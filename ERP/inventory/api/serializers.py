# Inventory/api/serializers.py
"""
REST API Serializers for Inventory vertical features
"""
from rest_framework import serializers
from ..models import (
    Product, ProductCategory, Warehouse, Location, Batch,
    InventoryItem, StockLedger, PriceList, PriceListItem,
    CustomerPriceList, PromotionRule, TransitWarehouse,
    PickList, PickListLine, PackingSlip, Shipment,
    Backorder, RMA, RMALine
)


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = '__all__'
        read_only_fields = ('organization',)


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = '__all__'
        read_only_fields = ('organization',)


class LocationSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    
    class Meta:
        model = Location
        fields = '__all__'


class BatchSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    
    class Meta:
        model = Batch
        fields = '__all__'
        read_only_fields = ('organization',)


class InventoryItemSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    
    class Meta:
        model = InventoryItem
        fields = '__all__'
        read_only_fields = ('organization', 'updated_at')


class StockLedgerSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    
    class Meta:
        model = StockLedger
        fields = '__all__'
        read_only_fields = ('organization', 'created_at')


# Pricing Models
class PriceListSerializer(serializers.ModelSerializer):
    items_count = serializers.IntegerField(source='items.count', read_only=True)
    
    class Meta:
        model = PriceList
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')


class PriceListItemSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    price_list_name = serializers.CharField(source='price_list.name', read_only=True)
    
    class Meta:
        model = PriceListItem
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class CustomerPriceListSerializer(serializers.ModelSerializer):
    price_list_name = serializers.CharField(source='price_list.name', read_only=True)
    
    class Meta:
        model = CustomerPriceList
        fields = '__all__'
        read_only_fields = ('organization', 'created_at')


class PromotionRuleSerializer(serializers.ModelSerializer):
    products_count = serializers.IntegerField(source='apply_to_products.count', read_only=True)
    is_valid_now = serializers.BooleanField(source='is_valid', read_only=True)
    
    class Meta:
        model = PromotionRule
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')


# Fulfillment Models
class TransitWarehouseSerializer(serializers.ModelSerializer):
    from_warehouse_name = serializers.CharField(source='from_warehouse.name', read_only=True)
    to_warehouse_name = serializers.CharField(source='to_warehouse.name', read_only=True)
    
    class Meta:
        model = TransitWarehouse
        fields = '__all__'
        read_only_fields = ('organization', 'created_at')


class PickListLineSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = PickListLine
        fields = '__all__'


class PickListSerializer(serializers.ModelSerializer):
    lines = PickListLineSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    
    class Meta:
        model = PickList
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')


class PackingSlipSerializer(serializers.ModelSerializer):
    pick_list_number = serializers.CharField(source='pick_list.pick_number', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    
    class Meta:
        model = PackingSlip
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')


class ShipmentSerializer(serializers.ModelSerializer):
    packing_number = serializers.CharField(source='packing_slip.packing_number', read_only=True)
    warehouse_name = serializers.CharField(source='ship_from_warehouse.name', read_only=True)
    
    class Meta:
        model = Shipment
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')


class BackorderSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    remaining_quantity = serializers.DecimalField(source='quantity_remaining', max_digits=15, decimal_places=4, read_only=True)
    
    class Meta:
        model = Backorder
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')


class RMALineSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = RMALine
        fields = '__all__'


class RMASerializer(serializers.ModelSerializer):
    lines = RMALineSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True, allow_null=True)
    
    class Meta:
        model = RMA
        fields = '__all__'
        read_only_fields = ('organization', 'created_at', 'updated_at')
