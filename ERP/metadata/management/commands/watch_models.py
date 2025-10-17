from django.core.management.base import BaseCommand
from django.conf import settings
import logging
import time
import signal
import sys

from ...watcher import start_watcher, stop_watcher

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Start watching model files for changes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stop',
            action='store_true',
            help='Stop the watcher instead of starting it',
        )

    def handle(self, *args, **options):
        if options['stop']:
            self.stdout.write(self.style.WARNING('Stopping model watcher...'))
            stop_watcher()
            self.stdout.write(self.style.SUCCESS('Model watcher stopped'))
            return

        if not settings.DEBUG:
            self.stdout.write(self.style.WARNING(
                'Warning: Running watcher in production mode. '
                'This is not recommended.'
            ))
            if input('Continue anyway? [y/N] ').lower() != 'y':
                return

        self.stdout.write(self.style.SUCCESS('Starting model watcher...'))
        
        # Handle graceful shutdown
        def signal_handler(signum, frame):
            self.stdout.write(self.style.WARNING('\nStopping watcher...'))
            stop_watcher()
            self.stdout.write(self.style.SUCCESS('Watcher stopped'))
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            start_watcher()
            self.stdout.write(self.style.SUCCESS('Model watcher started'))
            self.stdout.write('Press Ctrl+C to stop watching')
            
            # Keep the process running
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nStopping watcher...'))
            stop_watcher()
            self.stdout.write(self.style.SUCCESS('Watcher stopped'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            sys.exit(1) 