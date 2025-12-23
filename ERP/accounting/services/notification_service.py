from django.core.mail import send_mail
from django.conf import settings
from accounting.models import Vendor, ApprovalWorkflow
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending notifications (email, SMS) for various events.
    """

    @staticmethod
    def send_approval_notification(transaction_id, approvers, transaction_type='purchase_invoice'):
        """
        Send approval request notification to designated approvers.
        """
        try:
            subject = f"Approval Required: {transaction_type.replace('_', ' ').title()} #{transaction_id}"
            message = f"""
            A new {transaction_type.replace('_', ' ')} requires your approval.

            Transaction ID: {transaction_id}
            Please review and approve/reject in the system.

            Link: {settings.SITE_URL}/accounting/{transaction_type}/{transaction_id}/approve/
            """

            recipient_list = [approver.email for approver in approvers if approver.email]
            if recipient_list:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                logger.info(f"Approval notification sent for {transaction_type} {transaction_id}")
        except Exception as e:
            logger.error(f"Failed to send approval notification: {e}")

    @staticmethod
    def send_vendor_notification(vendor_id, subject, message, transaction_id=None):
        """
        Send notification to vendor (e.g., invoice ready, payment due).
        """
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            if vendor.email:
                full_subject = f"Himalytix ERP: {subject}"
                full_message = f"""
                Dear {vendor.name},

                {message}

                {"Transaction ID: " + str(transaction_id) if transaction_id else ""}

                Please login to your portal for more details.

                Regards,
                Himalytix ERP Team
                """

                send_mail(
                    subject=full_subject,
                    message=full_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[vendor.email],
                    fail_silently=False,
                )
                logger.info(f"Vendor notification sent to {vendor.email}")
        except Vendor.DoesNotExist:
            logger.warning(f"Vendor {vendor_id} not found for notification")
        except Exception as e:
            logger.error(f"Failed to send vendor notification: {e}")

    @staticmethod
    def send_low_stock_alert(product_id, current_stock, reorder_level):
        """
        Send alert for low stock items.
        """
        try:
            subject = f"Low Stock Alert: Product {product_id}"
            message = f"""
            Product {product_id} is running low on stock.

            Current Stock: {current_stock}
            Reorder Level: {reorder_level}

            Please reorder to avoid stockouts.
            """

            # Send to inventory managers (assuming a group or specific emails)
            recipient_list = getattr(settings, 'INVENTORY_MANAGERS', [])
            if recipient_list:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                logger.info(f"Low stock alert sent for product {product_id}")
        except Exception as e:
            logger.error(f"Failed to send low stock alert: {e}")

    @staticmethod
    def send_payment_reminder(vendor_id, due_amount, due_date):
        """
        Send payment due reminder to vendor.
        """
        NotificationService.send_vendor_notification(
            vendor_id=vendor_id,
            subject="Payment Due Reminder",
            message=f"""
            This is a reminder that payment of NPR {due_amount} is due on {due_date}.

            Please ensure timely payment to avoid any penalties.
            """,
        )

    @staticmethod
    def send_transaction_status_update(transaction_id, status, recipients):
        """
        Send status update notification for transactions.
        """
        try:
            subject = f"Transaction Status Update: {transaction_id}"
            message = f"""
            The status of transaction {transaction_id} has been updated to: {status}

            Please check the system for details.
            """

            recipient_list = [r.email for r in recipients if hasattr(r, 'email') and r.email]
            if recipient_list:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                logger.info(f"Status update notification sent for transaction {transaction_id}")
        except Exception as e:
            logger.error(f"Failed to send status update notification: {e}")

    @staticmethod
    def send_error_notification(error_message, recipients=None):
        """
        Send system error notifications to admins.
        """
        try:
            subject = "ERP System Error Alert"
            message = f"""
            An error occurred in the ERP system:

            {error_message}

            Please investigate immediately.
            """

            recipient_list = recipients or getattr(settings, 'ADMIN_EMAILS', [])
            if recipient_list:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                logger.error(f"Error notification sent: {error_message}")
        except Exception as e:
            logger.critical(f"Failed to send error notification: {e}")