# accounting/settings/ird_settings.py
"""
IRD (Inland Revenue Department) E-Billing Configuration Settings
These settings should be added to your Django settings.py or environment variables
"""

# =============================================
# IRD API Configuration
# =============================================

# IRD API Base URL
# Production: https://ird.gov.np/api/v1
# Testing: https://test.ird.gov.np/api/v1
IRD_API_URL = 'https://test.ird.gov.np/api/v1'

# IRD Credentials (should be in environment variables for production)
IRD_USERNAME = ''  # Your IRD username
IRD_PASSWORD = ''  # Your IRD password
IRD_SELLER_PAN = ''  # Your organization's PAN number

# API Timeout (seconds)
IRD_API_TIMEOUT = 30

# Retry configuration for failed submissions
IRD_MAX_RETRIES = 3
IRD_RETRY_DELAY = 5  # seconds

# =============================================
# Real-time vs Batch Submission
# =============================================

# Enable real-time submission (submit immediately when invoice is posted)
IRD_REALTIME_SUBMISSION = True

# Enable automatic retry for failed submissions
IRD_AUTO_RETRY_FAILED = True

# Maximum age (in days) for auto-retry of failed submissions
IRD_RETRY_MAX_AGE_DAYS = 7

# =============================================
# Fiscal Year Configuration
# =============================================

# Bikram Sambat to Gregorian conversion offset
# Nepal is approximately 56.7 years ahead
BS_TO_AD_OFFSET = 56.7

# Fiscal year start date (Nepal: mid-July, Shrawan 1)
FISCAL_YEAR_START_MONTH = 7
FISCAL_YEAR_START_DAY = 16

# =============================================
# QR Code Configuration
# =============================================

# QR Code version (1-40)
IRD_QR_VERSION = 1

# QR Code error correction level
# L: ~7% error correction
# M: ~15% error correction
# Q: ~25% error correction
# H: ~30% error correction
IRD_QR_ERROR_CORRECTION = 'L'

# QR Code box size (pixels per box)
IRD_QR_BOX_SIZE = 10

# QR Code border size (boxes)
IRD_QR_BORDER = 4

# =============================================
# Invoice Validation Rules
# =============================================

# Require customer PAN for invoices above this amount
IRD_PAN_REQUIRED_THRESHOLD = 100000  # NPR

# Minimum invoice amount for IRD submission
IRD_MIN_INVOICE_AMOUNT = 1

# Maximum invoice amount (for validation)
IRD_MAX_INVOICE_AMOUNT = 100000000  # 100 million NPR

# =============================================
# Logging and Audit
# =============================================

# Enable detailed IRD API logging
IRD_DETAILED_LOGGING = True

# Log directory for IRD transactions
IRD_LOG_DIR = 'logs/ird'

# Store IRD responses in database
IRD_STORE_RESPONSES = True

# Track reprint count
IRD_TRACK_REPRINTS = True

# Maximum allowed reprints before alert
IRD_MAX_REPRINT_WARNING = 5

# =============================================
# Cache Configuration
# =============================================

# Cache IRD configuration (seconds)
IRD_CONFIG_CACHE_TIMEOUT = 3600  # 1 hour

# Cache fiscal year mappings (seconds)
IRD_FISCAL_YEAR_CACHE_TIMEOUT = 86400  # 24 hours

# =============================================
# Email Notifications
# =============================================

# Send email notification on IRD submission failure
IRD_EMAIL_ON_FAILURE = True

# Email recipients for IRD failure notifications
IRD_FAILURE_EMAIL_RECIPIENTS = [
    'accounts@example.com',
    'admin@example.com',
]

# Send daily summary of IRD submissions
IRD_DAILY_SUMMARY_EMAIL = True

# =============================================
# Feature Flags
# =============================================

# Enable IRD integration (master switch)
IRD_INTEGRATION_ENABLED = True

# Enable invoice cancellation in IRD
IRD_ALLOW_CANCELLATION = True

# Enable batch submission
IRD_ALLOW_BATCH_SUBMISSION = True

# Require IRD sync before printing
IRD_REQUIRE_SYNC_BEFORE_PRINT = False

# =============================================
# Testing Mode
# =============================================

# Use IRD testing environment
IRD_TESTING_MODE = True

# Mock IRD API responses (for development)
IRD_MOCK_API = False

# =============================================
# Performance Settings
# =============================================

# Use Celery for async IRD submissions
IRD_USE_ASYNC_SUBMISSION = False

# Celery task retry settings
IRD_CELERY_MAX_RETRIES = 3
IRD_CELERY_RETRY_DELAY = 300  # 5 minutes

# Batch size for bulk submissions
IRD_BATCH_SUBMISSION_SIZE = 50

# =============================================
# Security Settings
# =============================================

# Encrypt IRD credentials in database
IRD_ENCRYPT_CREDENTIALS = True

# Require SSL/TLS for IRD API calls
IRD_REQUIRE_SSL = True

# Validate IRD SSL certificates
IRD_VERIFY_SSL_CERT = True

# =============================================
# Compliance Settings
# =============================================

# Prevent editing of IRD-synced invoices
IRD_LOCK_SYNCED_INVOICES = True

# Require cancellation reason
IRD_REQUIRE_CANCELLATION_REASON = True

# Minimum length for cancellation reason
IRD_CANCELLATION_REASON_MIN_LENGTH = 10

# Audit trail retention (days)
IRD_AUDIT_RETENTION_DAYS = 2555  # 7 years as per Nepal tax law

# =============================================
# Example Django Settings Integration
# =============================================

"""
# Add to your settings.py:

# IRD E-Billing Settings
from accounting.settings.ird_settings import *

# Override with environment variables (recommended for production)
import os

IRD_API_URL = os.getenv('IRD_API_URL', IRD_API_URL)
IRD_USERNAME = os.getenv('IRD_USERNAME', '')
IRD_PASSWORD = os.getenv('IRD_PASSWORD', '')
IRD_SELLER_PAN = os.getenv('IRD_SELLER_PAN', '')
IRD_TESTING_MODE = os.getenv('IRD_TESTING_MODE', 'true').lower() == 'true'
"""

# =============================================
# Example .env file
# =============================================

"""
# .env
IRD_API_URL=https://test.ird.gov.np/api/v1
IRD_USERNAME=your_username
IRD_PASSWORD=your_password
IRD_SELLER_PAN=123456789
IRD_TESTING_MODE=true
IRD_INTEGRATION_ENABLED=true
"""
