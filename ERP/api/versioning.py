"""
API Versioning Middleware
Handles API versioning via URL path and adds deprecation headers
"""
import re
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse


class APIVersionMiddleware(MiddlewareMixin):
    """
    Middleware to handle API versioning and deprecation warnings.
    
    Features:
    - Extracts version from URL path (/api/v1/, /api/v2/)
    - Adds API-Version header to responses
    - Adds Deprecation and Sunset headers for deprecated versions
    - Blocks requests to unsupported API versions
    """
    
    # Supported API versions
    SUPPORTED_VERSIONS = ['v1']
    DEFAULT_VERSION = 'v1'
    
    # Deprecated versions with sunset dates
    DEPRECATED_VERSIONS = {
        # 'v0': '2025-12-31',  # Example: v0 deprecated, sunset date
    }
    
    def process_request(self, request):
        """Extract API version from URL path"""
        # Match /api/v{number}/ pattern
        version_pattern = r'/api/(v\d+)/'
        match = re.search(version_pattern, request.path)
        
        if match:
            version = match.group(1)
            request.api_version = version
            
            # Check if version is supported
            if version not in self.SUPPORTED_VERSIONS:
                return HttpResponse(
                    content=f'{{"error": "API version {version} is not supported. '
                            f'Supported versions: {", ".join(self.SUPPORTED_VERSIONS)}"}}',
                    status=400,
                    content_type='application/json'
                )
        else:
            # No version in URL, use default
            request.api_version = self.DEFAULT_VERSION
    
    def process_response(self, request, response):
        """Add versioning headers to API responses"""
        # Only add headers to API requests
        if hasattr(request, 'api_version') and request.path.startswith('/api/'):
            version = request.api_version
            
            # Add API-Version header
            response['API-Version'] = version
            
            # Add deprecation headers if version is deprecated
            if version in self.DEPRECATED_VERSIONS:
                response['Deprecation'] = 'true'
                response['Sunset'] = self.DEPRECATED_VERSIONS[version]
                response['Link'] = '</api/v1/>; rel="successor-version"'
            
            # Add CORS headers for API responses (if needed)
            # response['Access-Control-Expose-Headers'] = 'API-Version, Deprecation, Sunset'
        
        return response
