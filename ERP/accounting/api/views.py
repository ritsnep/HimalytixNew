from rest_framework import status, viewsets, mixins, permissions
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiTypes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from django.http import HttpResponse
from accounting.models import (
    APPayment,
    ARReceipt,
    Asset,
    BankAccount,
    ConfigurableField,
    Customer,
    FieldConfig,
    IntegrationEvent,
    Journal,
    JournalLine,
    PurchaseInvoice,
    SalesInvoice,
    Vendor,
    VoucherLine,
    VoucherType,
)

from usermanagement.utils import PermissionUtils
from accounting.services.post_journal import post_journal
from .serializers import (
    APPaymentSerializer,
    ARReceiptSerializer,
    AssetSerializer,
    BankAccountSerializer,
    ConfigurableFieldSerializer,
    CustomerSerializer,
    FieldConfigSerializer,
    IntegrationEventSerializer,
    PurchaseInvoiceSerializer,
    SalesInvoiceSerializer,
    VendorSerializer,
    VoucherLineSerializer,
    VoucherTypeSerializer,
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Suggest journal entry descriptions",
    description="Returns frequently used journal entry descriptions based on historical data"
)
def suggest_journal_entries(request):
    """
    Suggests journal entries based on historical data.
    """
    organization = request.user.get_active_organization()
    if not organization:
        return Response({'detail': 'Active organization required'}, status=status.HTTP_400_BAD_REQUEST)
    if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'view'):
        return Response({'detail': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    suggestions = (
        Journal.objects.filter(organization=organization)
        .values('description')
        .annotate(count=Count('description'))
        .order_by('-count')[:5]
    )
    return Response([s['description'] for s in suggestions])

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Suggest journal entry lines",
    description="Returns suggested account lines for a journal entry based on description"
)
def get_line_suggestions(request):
    """
    Suggests lines to complete an entry based on the provided description.
    """
    organization = request.user.get_active_organization()
    if not organization:
        return Response({'detail': 'Active organization required'}, status=status.HTTP_400_BAD_REQUEST)
    if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'view'):
        return Response({'detail': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    description = request.GET.get('description')
    if not description:
        return Response([])

    lines = (
        JournalLine.objects.filter(
            journal__description=description,
            journal__organization=organization,
        )
        .values('account__account_code', 'account__account_name', 'debit_amount', 'credit_amount')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    
    suggestions = []
    for line in lines:
        suggestions.append({
            'account_code': line['account__account_code'],
            'account_name': line['account__account_name'],
            'debit_amount': line['debit_amount'],
            'credit_amount': line['credit_amount'],
        })

    return Response(suggestions)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Validate journal entry field",
    description="Validates a single field value from the journal entry form"
)
def validate_field(request):
    """
    Validates a single field from the journal entry form.
    """
    organization = request.user.get_active_organization()
    if not organization:
        return Response({'detail': 'Active organization required'}, status=status.HTTP_400_BAD_REQUEST)
    if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'change'):
        return Response({'detail': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    field_name = request.data.get('field_name')
    field_value = request.data.get('field_value')
    
    # This is a simplified example. A real implementation would use a
    # form to validate the field and return the specific error message.
    if field_name == 'reference' and len(field_value) > 100:
        return Response({'error': 'Reference cannot be longer than 100 characters.'}, status=400)
        
    return Response({'success': True})

from rest_framework.views import APIView
from rest_framework import serializers

class JournalBulkActionView(APIView):
    permission_classes = [IsAuthenticated]
    class RequestSerializer(serializers.Serializer):
        action = serializers.ChoiceField(choices=['post','delete','approve','reject','submit','reverse'])
        journal_ids = serializers.ListField(child=serializers.IntegerField(min_value=1))

    class ResponseSerializer(serializers.Serializer):
        success = serializers.BooleanField()
        deleted = serializers.IntegerField(required=False)
        posted = serializers.IntegerField(required=False)
        message = serializers.CharField(required=False)

    @extend_schema(request=RequestSerializer, responses={200: ResponseSerializer})

    def post(self, request, *args, **kwargs):
        serializer = self.RequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        journal_ids = serializer.validated_data['journal_ids']

        if not action or not journal_ids:
            return Response({'error': 'Missing action or journal_ids'}, status=status.HTTP_400_BAD_REQUEST)

        organization = request.user.get_active_organization()
        if not organization:
            return Response({'error': 'Active organization required'}, status=status.HTTP_400_BAD_REQUEST)
        permission_map = {
            'post': ('accounting', 'journal', 'post_journal'),
            'delete': ('accounting', 'journal', 'delete'),
            'approve': ('accounting', 'journal', 'approve_journal'),
            'reject': ('accounting', 'journal', 'reject_journal'),
            'submit': ('accounting', 'journal', 'submit_journal'),
            'reverse': ('accounting', 'journal', 'reverse_journal'),
        }

        permission_tuple = permission_map.get(action)
        if permission_tuple and not PermissionUtils.has_permission(request.user, organization, *permission_tuple):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        journals = Journal.objects.filter(id__in=journal_ids, organization=organization)

        if action == 'delete':
            deleted_count = journals.delete()[0]
            resp = self.ResponseSerializer({'success': True, 'deleted': deleted_count})
            return Response(resp.data)
            if action == 'post':
                posted = 0
                failures = []
                from accounting.services.post_journal import (
                    post_journal as service_post_journal,
                    JournalPostingError,
                    JournalValidationError,
                    format_journal_exception,
                )
                for journal in journals:
                    if journal.status == 'approved':
                        try:
                            service_post_journal(journal, request.user)
                            posted += 1
                        except (JournalPostingError, JournalValidationError) as exc:
                            failures.append({'journal_id': journal.pk, 'error': format_journal_exception(exc)})
                if failures:
                    return Response({'success': False, 'posted': posted, 'failures': failures}, status=status.HTTP_207_MULTI_STATUS)
                resp = self.ResponseSerializer({'success': True, 'posted': posted})
                return Response(resp.data)

        resp = self.ResponseSerializer({'success': True, 'message': f'Action {action} acknowledged for {journals.count()} journals.'})
        return Response(resp.data, status=status.HTTP_200_OK)

class OrganizationScopedMixin:
    permission_classes = [IsAuthenticated]
    def get_organization(self):
        return self.request.user.get_active_organization()

    def get_queryset(self):
        org = self.get_organization()
        if not org:
            return self.queryset.none()
        return self.queryset.filter(organization=org)


class VendorViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = VendorSerializer
    queryset = Vendor.objects.all()


class CustomerViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()


class PurchaseInvoiceViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = PurchaseInvoiceSerializer
    queryset = PurchaseInvoice.objects.select_related('vendor')


class SalesInvoiceViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = SalesInvoiceSerializer
    queryset = SalesInvoice.objects.select_related('customer')


class APPaymentViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = APPaymentSerializer
    queryset = APPayment.objects.select_related('vendor')


class ARReceiptViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ARReceiptSerializer
    queryset = ARReceipt.objects.select_related('customer')


class BankAccountViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = BankAccountSerializer
    queryset = BankAccount.objects.all()


class AssetViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AssetSerializer
    queryset = Asset.objects.select_related('category')


class IntegrationEventViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = IntegrationEventSerializer
    queryset = IntegrationEvent.objects.all()

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return IntegrationEvent.objects.none()
        return IntegrationEvent.objects.filter(
            payload__organization_id=getattr(organization, 'id', None)
        )


from .serializers import JournalLineSerializer, VoucherLineSerializer
from accounting.services.voucher_config import VoucherConfigResolver, VoucherConfigManager


class JournalLineViewSet(OrganizationScopedMixin, mixins.CreateModelMixin,
                         mixins.UpdateModelMixin, mixins.DestroyModelMixin,
                         mixins.RetrieveModelMixin, mixins.ListModelMixin,
                         viewsets.GenericViewSet):
    """Minimal REST API for JournalLine create/update/delete to support UI and integration tests."""
    serializer_class = JournalLineSerializer
    queryset = JournalLine.objects.select_related('journal', 'account')

    def perform_create(self, serializer):
        journal = serializer.validated_data.get('journal')
        # Permission check
        org = self.get_organization()
        if not org or journal.organization_id != org.id:
            raise permissions.PermissionDenied()
        # Set created_by
        serializer.save(created_by=self.request.user)
        # Update totals and balanced flag
        journal.update_totals()
        journal.save()

    def perform_update(self, serializer):
        journal = serializer.instance.journal
        if journal.organization_id != self.get_organization().id:
            raise permissions.PermissionDenied()
        serializer.save(updated_by=self.request.user)
        journal.update_totals()
        journal.save()

    def perform_destroy(self, instance):
        journal = instance.journal
        if journal.organization_id != self.get_organization().id:
            raise permissions.PermissionDenied()
        instance.delete()
        journal.update_totals()
        journal.save()


class VoucherLineViewSet(OrganizationScopedMixin, mixins.CreateModelMixin,
                         mixins.UpdateModelMixin, mixins.DestroyModelMixin,
                         mixins.RetrieveModelMixin, mixins.ListModelMixin,
                         viewsets.GenericViewSet):
    """REST API for VoucherLine CRUD operations to support HTMX voucher entry."""
    serializer_class = VoucherLineSerializer
    queryset = VoucherLine.objects.select_related('journal', 'account')

    def get_serializer_class(self):
        if self.request.META.get('HTTP_ACCEPT', '').startswith('text/html'):
            return None  # We'll handle HTML rendering manually
        return VoucherLineSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        
        if hasattr(self, 'response'):
            return self.response
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_update(serializer)
        
        if hasattr(self, 'response'):
            return self.response
        
        return Response(serializer.data)

    def perform_create(self, serializer):
        journal = serializer.validated_data.get('journal')
        # Permission check
        org = self.get_organization()
        if not org or journal.organization_id != org.id:
            raise permissions.PermissionDenied()
        # Set created_by
        instance = serializer.save(created_by=self.request.user)
        
        # If HTMX request, prepare HTML response
        if self.request.META.get('HTTP_ACCEPT', '').startswith('text/html'):
            self._render_html_response(instance, 'create')
        return instance

    def perform_update(self, serializer):
        journal = serializer.instance.journal
        if journal.organization_id != self.get_organization().id:
            raise permissions.PermissionDenied()
        instance = serializer.save(updated_by=self.request.user)
        
        # If HTMX request, prepare HTML response
        if self.request.META.get('HTTP_ACCEPT', '').startswith('text/html'):
            self._render_html_response(instance, 'update')
        return instance

    def perform_destroy(self, instance):
        journal = instance.journal
        if journal.organization_id != self.get_organization().id:
            raise permissions.PermissionDenied()
        instance.delete()

    def _render_html_response(self, instance, action):
        """Render HTML response for HTMX requests."""
        from django.template.loader import render_to_string
        from accounting.forms_factory import VoucherFormFactory
        
        organization = self.get_organization()
        # Create a form populated with the instance data
        form = VoucherFormFactory.get_journal_line_form(
            organization=organization,
            instance=instance,  # This should work if VoucherLine is compatible
            prefix=f'lines-{instance.line_number - 1}'
        )
        
        context = {
            'form': form,
            'form_index': instance.line_number - 1,
            'organization': organization,
            'line': instance,
        }
        
        html = render_to_string('accounting/partials/journal_line_form.html', context)
        self.response = HttpResponse(html, content_type='text/html')


class VoucherViewSet(OrganizationScopedMixin, mixins.RetrieveModelMixin,
                     mixins.ListModelMixin, viewsets.GenericViewSet):
    """ViewSet for Voucher (Journal) operations."""
    serializer_class = None  # We'll add if needed
    queryset = Journal.objects.select_related('organization', 'journal_type', 'period')

    def get_queryset(self):
        return super().get_queryset().filter(organization=self.get_organization())


class VoucherTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for VoucherType management."""
    serializer_class = VoucherTypeSerializer
    queryset = VoucherType.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class ConfigurableFieldViewSet(viewsets.ModelViewSet):
    """ViewSet for ConfigurableField management."""
    serializer_class = ConfigurableFieldSerializer
    queryset = ConfigurableField.objects.select_related('voucher_type')
    permission_classes = [permissions.IsAuthenticated]


class FieldConfigViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    """ViewSet for FieldConfig management with organization scoping."""
    serializer_class = FieldConfigSerializer
    queryset = FieldConfig.objects.select_related('organization', 'field__voucher_type')

    def get_queryset(self):
        return super().get_queryset().filter(organization=self.get_organization())

    def perform_create(self, serializer):
        serializer.save(organization=self.get_organization())


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Get voucher configuration",
    description="Returns the effective field configuration for a voucher type and organization"
)
def get_voucher_config(request):
    """
    Get voucher configuration for the current organization and specified voucher type.
    """
    organization = request.user.get_active_organization()
    if not organization:
        return Response({'detail': 'Active organization required'}, status=status.HTTP_400_BAD_REQUEST)

    voucher_type_code = request.GET.get('voucher_type')
    if not voucher_type_code:
        return Response({'detail': 'voucher_type parameter required'}, status=status.HTTP_400_BAD_REQUEST)

    resolver = VoucherConfigManager.get_config_resolver(organization, voucher_type_code)
    if not resolver:
        return Response({'detail': 'Invalid voucher type'}, status=status.HTTP_400_BAD_REQUEST)

    config = resolver.get_fields_config()
    return Response(config)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_field_config(request, voucher_type_id, field_name):
    """
    Get configuration for a specific field.
    """
    try:
        organization = request.user.get_active_organization()
        voucher_type = VoucherType.objects.get(pk=voucher_type_id)

        # Try to get organization-specific config first, then fall back to default
        try:
            field_config = FieldConfig.objects.get(
                organization=organization,
                configurable_field__voucher_type=voucher_type,
                configurable_field__field_name=field_name
            )
            config_data = {
                'label': field_config.label,
                'field_type': field_config.field_type,
                'required': field_config.required,
                'visible': field_config.visible,
                'default_value': field_config.default_value,
                'help_text': field_config.help_text,
            }
        except FieldConfig.DoesNotExist:
            # Get default config
            try:
                default_field = ConfigurableField.objects.get(
                    voucher_type=voucher_type,
                    field_name=field_name
                )
                config_data = {
                    'label': default_field.label,
                    'field_type': default_field.field_type,
                    'required': default_field.required,
                    'visible': default_field.visible,
                    'default_value': default_field.default_value,
                    'help_text': default_field.help_text,
                }
            except ConfigurableField.DoesNotExist:
                return Response({'detail': 'Field not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(config_data)
    except VoucherType.DoesNotExist:
        return Response({'detail': 'Voucher type not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_field_config(request):
    """
    Save or update field configuration for an organization.
    """
    try:
        organization = request.user.get_active_organization()
        voucher_type_id = request.data.get('voucher_type')
        field_name = request.data.get('field_name')

        if not voucher_type_id or not field_name:
            return Response({'detail': 'voucher_type and field_name are required'}, status=status.HTTP_400_BAD_REQUEST)

        voucher_type = VoucherType.objects.get(pk=voucher_type_id)

        # Get or create the configurable field
        configurable_field, created = ConfigurableField.objects.get_or_create(
            voucher_type=voucher_type,
            field_name=field_name,
            defaults={
                'label': request.data.get('label', field_name),
                'field_type': request.data.get('field_type', 'text'),
                'required': request.data.get('required', False),
                'visible': request.data.get('visible', True),
                'default_value': request.data.get('default_value', ''),
                'help_text': request.data.get('help_text', ''),
            }
        )

        # Create or update organization-specific config
        field_config, created = FieldConfig.objects.update_or_create(
            organization=organization,
            configurable_field=configurable_field,
            defaults={
                'label': request.data.get('label'),
                'field_type': request.data.get('field_type'),
                'required': request.data.get('required', False),
                'visible': request.data.get('visible', True),
                'default_value': request.data.get('default_value'),
                'help_text': request.data.get('help_text'),
            }
        )

        return Response({
            'id': field_config.id,
            'message': 'Field configuration saved successfully'
        })
    except VoucherType.DoesNotExist:
        return Response({'detail': 'Voucher type not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_voucher_type_defaults(request, voucher_type_id):
    """
    Reset all field configurations for a voucher type to defaults.
    """
    try:
        organization = request.user.get_active_organization()
        voucher_type = VoucherType.objects.get(pk=voucher_type_id)

        # Delete all organization-specific configs for this voucher type
        FieldConfig.objects.filter(
            organization=organization,
            configurable_field__voucher_type=voucher_type
        ).delete()

        return Response({'message': 'Configurations reset to defaults'})
    except VoucherType.DoesNotExist:
        return Response({'detail': 'Voucher type not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
