from accounting.services.voucher_orchestrator import VoucherOrchestrator
from accounting.models import VoucherProcess


class VoucherConfigOrchestrator(VoucherOrchestrator):
    def process(self, voucher_id, commit_type, actor, idempotency_key):
        # Check idempotency
        if VoucherProcess.objects.filter(voucher_id=voucher_id, correlation_id=idempotency_key).exists():
            return {'success': True, 'message': 'Already processed'}
        
        # Enforce state machine
        voucher = self._get_voucher(voucher_id)
        if voucher.status != 'draft':
            raise ValueError("VCH-001: Invalid state")
        
        # Permission check
        if not self._has_permission(actor, 'direct_post'):
            voucher.status = 'pending_approval'
            voucher.save()
            return {'success': True, 'message': 'Pending approval'}
        
        # Create journal
        journal = self._create_journal(voucher)
        
        # Post GL
        self._post_gl(journal)
        
        # Post inventory if needed
        config = voucher.voucher_config
        if config.affects_inventory:
            self._post_inventory(journal)
        
        # Update status
        voucher.status = 'posted'
        voucher.save()
        
        VoucherProcess.objects.create(
            voucher=voucher,
            current_step='done',
            actor=actor,
            correlation_id=idempotency_key,
        )
        
        return {'success': True}
    
    def _post_gl(self, journal):
        # GL posting logic
        pass
    
    def _post_inventory(self, journal):
        # Inventory posting
        pass