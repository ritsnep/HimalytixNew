"""
Management command to warm application caches
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.contrib.auth import get_user_model
from utils.view_caching import warm_cache_batch
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class Command(BaseCommand):
    help = 'Warm application caches with frequently accessed data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scope',
            type=str,
            default='all',
            choices=['all', 'homepage', 'users', 'stats'],
            help='Scope of cache warming (default: all)',
        )
        
        parser.add_argument(
            '--user-limit',
            type=int,
            default=100,
            help='Maximum number of user caches to warm (default: 100)',
        )

    def handle(self, *args, **options):
        scope = options['scope']
        user_limit = options['user_limit']
        
        self.stdout.write(self.style.SUCCESS(f'🔥 Starting cache warming (scope: {scope})...'))
        
        total_warmed = 0
        
        if scope in ['all', 'homepage']:
            total_warmed += self.warm_homepage_caches()
        
        if scope in ['all', 'stats']:
            total_warmed += self.warm_stats_caches()
        
        if scope in ['all', 'users']:
            total_warmed += self.warm_user_caches(limit=user_limit)
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Cache warming complete! {total_warmed} entries warmed.')
        )
    
    def warm_homepage_caches(self):
        """Warm homepage-related caches."""
        self.stdout.write('📄 Warming homepage caches...')
        
        cache_specs = [
            {
                'key': 'homepage:features',
                'data_func': self._get_features,
                'timeout': 3600,  # 1 hour
            },
            {
                'key': 'homepage:stats',
                'data_func': self._get_homepage_stats,
                'timeout': 600,  # 10 minutes
            },
            {
                'key': 'homepage:recent_entries',
                'data_func': self._get_recent_entries,
                'timeout': 300,  # 5 minutes
            },
        ]
        
        results = warm_cache_batch(cache_specs)
        count = sum(results.values())
        
        self.stdout.write(f'  ✓ {count} homepage caches warmed')
        return count
    
    def warm_stats_caches(self):
        """Warm statistics caches."""
        self.stdout.write('📊 Warming statistics caches...')
        
        cache_specs = [
            {
                'key': 'stats:global',
                'data_func': self._get_global_stats,
                'timeout': 300,
            },
            {
                'key': 'stats:monthly',
                'data_func': self._get_monthly_stats,
                'timeout': 600,
            },
            {
                'key': 'stats:yearly',
                'data_func': self._get_yearly_stats,
                'timeout': 1800,
            },
        ]
        
        results = warm_cache_batch(cache_specs)
        count = sum(results.values())
        
        self.stdout.write(f'  ✓ {count} statistics caches warmed')
        return count
    
    def warm_user_caches(self, limit=100):
        """Warm user-specific caches."""
        self.stdout.write(f'👥 Warming user caches (limit: {limit})...')
        
        # Get recently active users
        users = User.objects.filter(
            is_active=True
        ).order_by('-last_login')[:limit]
        
        count = 0
        for user in users:
            # Warm dashboard cache
            cache_key = f'dashboard:user:{user.id}'
            try:
                data = {
                    'entries': self._get_user_entries(user),
                    'notifications': self._get_user_notifications(user),
                    'stats': self._get_user_stats(user),
                }
                cache.set(cache_key, data, 300)
                count += 1
            except Exception as e:
                logger.error(f'Failed to warm cache for user {user.id}: {e}')
        
        self.stdout.write(f'  ✓ {count} user caches warmed')
        return count
    
    # =========================================================================
    # DATA FETCHING METHODS
    # =========================================================================
    
    def _get_features(self):
        """Get application features."""
        return [
            {'name': 'Multi-tenant', 'description': 'Support multiple organizations'},
            {'name': 'Journal Entries', 'description': 'Track financial transactions'},
            {'name': 'Reporting', 'description': 'Generate financial reports'},
        ]
    
    def _get_homepage_stats(self):
        """Get homepage statistics."""
        from journal.models import JournalEntry
        
        return {
            'total_users': User.objects.filter(is_active=True).count(),
            'total_entries': JournalEntry.objects.count(),
            'active_today': User.objects.filter(
                last_login__date=timezone.now().date()
            ).count(),
        }
    
    def _get_recent_entries(self):
        """Get recent journal entries."""
        from journal.models import JournalEntry
        
        entries = JournalEntry.objects.order_by('-created_at')[:10]
        
        return [
            {
                'id': e.id,
                'date': e.date.isoformat(),
                'description': e.description,
                'amount': float(e.amount),
            }
            for e in entries
        ]
    
    def _get_global_stats(self):
        """Get global statistics."""
        from journal.models import JournalEntry
        from django.db.models import Sum, Count
        
        stats = JournalEntry.objects.aggregate(
            total_amount=Sum('amount'),
            total_count=Count('id'),
        )
        
        return {
            'total_amount': float(stats['total_amount'] or 0),
            'total_entries': stats['total_count'] or 0,
            'total_users': User.objects.count(),
        }
    
    def _get_monthly_stats(self):
        """Get monthly statistics."""
        from journal.models import JournalEntry
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0)
        
        monthly_total = JournalEntry.objects.filter(
            date__gte=month_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return {
            'month': now.strftime('%B %Y'),
            'total_amount': float(monthly_total),
        }
    
    def _get_yearly_stats(self):
        """Get yearly statistics."""
        from journal.models import JournalEntry
        from django.db.models import Sum
        from django.utils import timezone
        
        year = timezone.now().year
        
        yearly_total = JournalEntry.objects.filter(
            date__year=year
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return {
            'year': year,
            'total_amount': float(yearly_total),
        }
    
    def _get_user_entries(self, user):
        """Get user journal entries."""
        from journal.models import JournalEntry
        
        entries = JournalEntry.objects.filter(
            created_by=user
        ).order_by('-date')[:10]
        
        return [
            {
                'id': e.id,
                'date': e.date.isoformat(),
                'description': e.description,
                'amount': float(e.amount),
            }
            for e in entries
        ]
    
    def _get_user_notifications(self, user):
        """Get user notifications."""
        # Placeholder - implement based on your notification system
        return []
    
    def _get_user_stats(self, user):
        """Get user statistics."""
        from journal.models import JournalEntry
        from django.db.models import Sum, Count
        
        stats = JournalEntry.objects.filter(
            created_by=user
        ).aggregate(
            total_amount=Sum('amount'),
            total_count=Count('id'),
        )
        
        return {
            'total_entries': stats['total_count'] or 0,
            'total_amount': float(stats['total_amount'] or 0),
        }
