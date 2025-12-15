"""
Notification System Utilities

Provides comprehensive notification handling for the accounting system,
including email notifications, in-app notifications, and notification templates.
"""

from typing import Optional, Dict, List, Any, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model

from .organization import OrganizationService

User = get_user_model()


class NotificationType(Enum):
    """Types of notifications."""
    EMAIL = 'email'
    IN_APP = 'in_app'
    SMS = 'sms'
    PUSH = 'push'


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'


class NotificationService:
    """
    Centralized notification service for sending various types of notifications.
    """

    def __init__(self, organization: Optional[Any] = None):
        self.organization = organization

    def send_notification(
        self,
        recipients: Union[User, List[User], str, List[str]],
        subject: str,
        message: str,
        notification_type: NotificationType = NotificationType.EMAIL,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        template_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Send notification to recipients.

        Args:
            recipients: User(s) or email address(es)
            subject: Notification subject
            message: Notification message
            notification_type: Type of notification
            priority: Notification priority
            template_name: Template to use for rendering
            context: Template context variables
            attachments: List of attachment dictionaries

        Returns:
            True if notification sent successfully
        """
        try:
            if notification_type == NotificationType.EMAIL:
                return self._send_email_notification(
                    recipients, subject, message, template_name, context, attachments
                )
            elif notification_type == NotificationType.IN_APP:
                return self._send_in_app_notification(
                    recipients, subject, message, priority
                )
            elif notification_type == NotificationType.SMS:
                return self._send_sms_notification(recipients, message)
            elif notification_type == NotificationType.PUSH:
                return self._send_push_notification(recipients, subject, message)
            else:
                return False
        except Exception as e:
            # Log error but don't raise exception
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send notification: {e}")
            return False

    def send_approval_notification(
        self,
        journal: Any,
        approvers: List[User],
        action: str = 'pending'
    ) -> bool:
        """
        Send journal approval notification.

        Args:
            journal: Journal instance
            approvers: List of approver users
            action: 'pending', 'approved', 'rejected'

        Returns:
            True if notification sent successfully
        """
        template_map = {
            'pending': 'journal_approval_pending',
            'approved': 'journal_approved',
            'rejected': 'journal_rejected'
        }

        template_name = template_map.get(action, 'journal_approval_pending')
        subject_map = {
            'pending': f'Journal Approval Required: {journal.journal_number}',
            'approved': f'Journal Approved: {journal.journal_number}',
            'rejected': f'Journal Rejected: {journal.journal_number}'
        }

        subject = subject_map.get(action, f'Journal Update: {journal.journal_number}')

        context = {
            'journal': journal,
            'action': action,
            'approvers': approvers,
            'organization': self.organization,
            'total_amount': journal.total_amount,
            'journal_date': journal.journal_date,
        }

        return self.send_notification(
            recipients=approvers,
            subject=subject,
            message='',  # Will be rendered from template
            notification_type=NotificationType.EMAIL,
            priority=NotificationPriority.HIGH,
            template_name=template_name,
            context=context
        )

    def send_payment_reminder(
        self,
        invoice: Any,
        customer: Any,
        days_overdue: int = 0
    ) -> bool:
        """
        Send payment reminder for overdue invoice.

        Args:
            invoice: Invoice instance
            customer: Customer instance
            days_overdue: Number of days overdue

        Returns:
            True if notification sent successfully
        """
        if days_overdue == 0:
            template_name = 'payment_due_soon'
            subject = f'Payment Due Soon - Invoice {invoice.invoice_number}'
            priority = NotificationPriority.MEDIUM
        else:
            template_name = 'payment_overdue'
            subject = f'OVERDUE: Payment Required - Invoice {invoice.invoice_number}'
            priority = NotificationPriority.HIGH

        context = {
            'invoice': invoice,
            'customer': customer,
            'days_overdue': days_overdue,
            'due_date': invoice.due_date,
            'amount_due': invoice.total_amount,
            'organization': self.organization,
        }

        # Get customer email
        recipient_email = getattr(customer, 'email', None)
        if not recipient_email:
            return False

        return self.send_notification(
            recipients=recipient_email,
            subject=subject,
            message='',
            notification_type=NotificationType.EMAIL,
            priority=priority,
            template_name=template_name,
            context=context
        )

    def send_low_stock_alert(
        self,
        product: Any,
        current_stock: Decimal,
        reorder_level: Decimal
    ) -> bool:
        """
        Send low stock alert notification.

        Args:
            product: Product instance
            current_stock: Current stock level
            reorder_level: Reorder level threshold

        Returns:
            True if notification sent successfully
        """
        subject = f'Low Stock Alert: {product.name}'
        context = {
            'product': product,
            'current_stock': current_stock,
            'reorder_level': reorder_level,
            'organization': self.organization,
        }

        # Get inventory managers for the organization
        inventory_managers = self._get_inventory_managers()

        if not inventory_managers:
            return False

        return self.send_notification(
            recipients=inventory_managers,
            subject=subject,
            message='',
            notification_type=NotificationType.EMAIL,
            priority=NotificationPriority.HIGH,
            template_name='low_stock_alert',
            context=context
        )

    def send_budget_alert(
        self,
        budget: Any,
        current_spending: Decimal,
        threshold_percentage: float
    ) -> bool:
        """
        Send budget threshold alert.

        Args:
            budget: Budget instance
            current_spending: Current spending amount
            threshold_percentage: Threshold percentage (e.g., 0.8 for 80%)

        Returns:
            True if notification sent successfully
        """
        subject = f'Budget Alert: {budget.name} - {threshold_percentage*100:.0f}% Utilized'

        context = {
            'budget': budget,
            'current_spending': current_spending,
            'budget_amount': budget.amount,
            'threshold_percentage': threshold_percentage,
            'remaining_budget': budget.amount - current_spending,
            'organization': self.organization,
        }

        # Get budget managers
        budget_managers = self._get_budget_managers()

        return self.send_notification(
            recipients=budget_managers,
            subject=subject,
            message='',
            notification_type=NotificationType.EMAIL,
            priority=NotificationPriority.HIGH,
            template_name='budget_alert',
            context=context
        )

    def _send_email_notification(
        self,
        recipients: Union[User, List[User], str, List[str]],
        subject: str,
        message: str,
        template_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send email notification."""
        # Extract email addresses
        email_addresses = self._extract_email_addresses(recipients)
        if not email_addresses:
            return False

        # Render message from template if provided
        if template_name and context is not None:
            try:
                html_message = render_to_string(f'notifications/{template_name}.html', context)
                text_message = render_to_string(f'notifications/{template_name}.txt', context)
            except Exception:
                # Fallback to plain message
                html_message = message
                text_message = message
        else:
            html_message = message
            text_message = message

        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            to=email_addresses
        )

        email.attach_alternative(html_message, "text/html")

        # Add attachments
        if attachments:
            for attachment in attachments:
                email.attach(
                    attachment['filename'],
                    attachment['content'],
                    attachment.get('mimetype', 'application/octet-stream')
                )

        # Send email
        try:
            email.send()
            return True
        except Exception:
            return False

    def _send_in_app_notification(
        self,
        recipients: Union[User, List[User], str, List[str]],
        subject: str,
        message: str,
        priority: NotificationPriority
    ) -> bool:
        """Send in-app notification."""
        # Extract users
        users = self._extract_users(recipients)
        if not users:
            return False

        # Create in-app notifications
        notifications_created = 0
        for user in users:
            try:
                from accounting.models import InAppNotification
                InAppNotification.objects.create(
                    user=user,
                    organization=self.organization,
                    title=subject,
                    message=message,
                    priority=priority.value,
                    is_read=False
                )
                notifications_created += 1
            except Exception:
                continue

        return notifications_created > 0

    def _send_sms_notification(self, recipients: Union[User, List[User], str, List[str]], message: str) -> bool:
        """Send SMS notification."""
        # This would integrate with SMS service provider
        # For now, just return False as placeholder
        return False

    def _send_push_notification(self, recipients: Union[User, List[User], str, List[str]], subject: str, message: str) -> bool:
        """Send push notification."""
        # This would integrate with push notification service
        # For now, just return False as placeholder
        return False

    def _extract_email_addresses(self, recipients: Union[User, List[User], str, List[str]]) -> List[str]:
        """Extract email addresses from various recipient formats."""
        emails = []

        if isinstance(recipients, (list, tuple)):
            for recipient in recipients:
                if isinstance(recipient, str):
                    emails.append(recipient)
                elif hasattr(recipient, 'email'):
                    emails.append(recipient.email)
        else:
            if isinstance(recipients, str):
                emails.append(recipients)
            elif hasattr(recipients, 'email'):
                emails.append(recipients.email)

        # Filter out None/empty emails
        return [email for email in emails if email]

    def _extract_users(self, recipients: Union[User, List[User], str, List[str]]) -> List[User]:
        """Extract User objects from various recipient formats."""
        users = []

        if isinstance(recipients, (list, tuple)):
            for recipient in recipients:
                if isinstance(recipient, User):
                    users.append(recipient)
        else:
            if isinstance(recipients, User):
                users.append(recipients)

        return users

    def _get_inventory_managers(self) -> List[User]:
        """Get users with inventory management role."""
        if not self.organization:
            return []

        # This would query users with inventory management permissions
        # For now, return empty list as placeholder
        return []

    def _get_budget_managers(self) -> List[User]:
        """Get users with budget management role."""
        if not self.organization:
            return []

        # This would query users with budget management permissions
        # For now, return empty list as placeholder
        return []


class NotificationManager:
    """
    Manages notification preferences and delivery settings.
    """

    def __init__(self, user: Optional[User] = None):
        self.user = user

    def get_user_preferences(self) -> Dict[str, Any]:
        """
        Get user's notification preferences.

        Returns:
            Dictionary of notification preferences
        """
        if not self.user:
            return self._get_default_preferences()

        # This would load from user preferences model
        # For now, return default preferences
        return self._get_default_preferences()

    def update_preferences(self, preferences: Dict[str, Any]) -> bool:
        """
        Update user's notification preferences.

        Args:
            preferences: New preferences dictionary

        Returns:
            True if updated successfully
        """
        if not self.user:
            return False

        # This would save to user preferences model
        # For now, just return True
        return True

    def _get_default_preferences(self) -> Dict[str, Any]:
        """Get default notification preferences."""
        return {
            'email_notifications': True,
            'in_app_notifications': True,
            'sms_notifications': False,
            'push_notifications': False,
            'approval_notifications': True,
            'budget_alerts': True,
            'inventory_alerts': True,
            'payment_reminders': True,
        }


class NotificationTemplate:
    """
    Manages notification templates.
    """

    @staticmethod
    def get_template(name: str, context: Dict[str, Any]) -> Tuple[str, str]:
        """
        Get notification template by name.

        Args:
            name: Template name
            context: Template context

        Returns:
            Tuple of (subject, message)
        """
        templates = {
            'journal_approval_pending': {
                'subject': 'Journal Approval Required: {{ journal.journal_number }}',
                'message': '''
                Dear {{ user.first_name }},

                A journal entry requires your approval:

                Journal Number: {{ journal.journal_number }}
                Date: {{ journal.journal_date }}
                Amount: {{ journal.total_amount }}
                Description: {{ journal.description }}

                Please review and approve/reject this journal entry.

                Best regards,
                {{ organization.name }} Accounting System
                '''
            },
            'low_stock_alert': {
                'subject': 'Low Stock Alert: {{ product.name }}',
                'message': '''
                Alert: Low Stock Level

                Product: {{ product.name }}
                Current Stock: {{ current_stock }}
                Reorder Level: {{ reorder_level }}

                Please reorder this product to avoid stockouts.

                {{ organization.name }}
                '''
            }
        }

        template = templates.get(name)
        if not template:
            return '', ''

        # Simple template rendering (in practice, use Django templates)
        subject = template['subject']
        message = template['message']

        for key, value in context.items():
            subject = subject.replace(f'{{{{ {key} }}}}', str(value))
            message = message.replace(f'{{{{ {key} }}}}', str(value))

            # Handle nested attributes
            if '.' in key:
                parts = key.split('.')
                if len(parts) == 2 and parts[0] in context:
                    obj = context[parts[0]]
                    attr = parts[1]
                    if hasattr(obj, attr):
                        value = getattr(obj, attr)
                        subject = subject.replace(f'{{{{ {key} }}}}', str(value))
                        message = message.replace(f'{{{{ {key} }}}}', str(value))

        return subject, message


# Utility functions for common notification patterns
def notify_journal_status_change(journal: Any, old_status: str, new_status: str) -> None:
    """
    Notify relevant users about journal status change.

    Args:
        journal: Journal instance
        old_status: Previous status
        new_status: New status
    """
    organization = getattr(journal, 'organization', None)
    service = NotificationService(organization)

    # Notify creator
    if hasattr(journal, 'created_by') and journal.created_by:
        service.send_notification(
            recipients=journal.created_by,
            subject=f'Journal Status Changed: {journal.journal_number}',
            message=f'Your journal {journal.journal_number} status changed from {old_status} to {new_status}',
            notification_type=NotificationType.IN_APP,
            priority=NotificationPriority.MEDIUM
        )

    # Notify approvers if status changed to approved/rejected
    if new_status in ['approved', 'rejected']:
        # Get approvers (this would depend on your approval workflow)
        approvers = []  # Would need to implement approver lookup
        if approvers:
            service.send_approval_notification(journal, approvers, new_status.lower())


def notify_payment_received(invoice: Any, payment: Any) -> None:
    """
    Notify about payment received.

    Args:
        invoice: Invoice instance
        payment: Payment instance
    """
    organization = getattr(invoice, 'organization', None)
    service = NotificationService(organization)

    # Notify customer
    if hasattr(invoice, 'customer') and hasattr(invoice.customer, 'email'):
        service.send_notification(
            recipients=invoice.customer.email,
            subject=f'Payment Received - Invoice {invoice.invoice_number}',
            message=f'We have received your payment of {payment.amount} for invoice {invoice.invoice_number}',
            notification_type=NotificationType.EMAIL,
            priority=NotificationPriority.MEDIUM
        )


def schedule_recurring_notifications() -> None:
    """
    Schedule recurring notification tasks.
    """
    # This would be called from a management command or cron job
    # to send recurring notifications like payment reminders, budget alerts, etc.

    # Example: Send overdue payment reminders
    # - Query overdue invoices
    # - Send reminders to customers
    # - Send alerts to accounting team

    # Example: Send budget utilization alerts
    # - Check budget utilization
    # - Send alerts when thresholds are reached

    pass
