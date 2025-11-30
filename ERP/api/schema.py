"""
drf-spectacular OpenAPI extensions for custom authentication classes.

These extensions allow drf-spectacular to properly document custom authentication
schemes in the generated OpenAPI schema.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object


class StreamlitTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    """OpenAPI extension for StreamlitTokenAuthentication.
    
    This tells drf-spectacular how to document endpoints that use
    StreamlitTokenAuthentication in the OpenAPI schema.
    """
    target_class = 'api.authentication.StreamlitTokenAuthentication'
    name = 'streamlitTokenAuth'

    def get_security_definition(self, auto_schema):
        return build_bearer_security_scheme_object(
            header_name='Authorization',
            token_prefix='Bearer',
            bearer_format='JWT',  # It's a signed token, similar to JWT format
        )


class TenantTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    """OpenAPI extension for TenantTokenAuthentication.
    
    This tells drf-spectacular how to document endpoints that use
    TenantTokenAuthentication in the OpenAPI schema.
    """
    target_class = 'api.authentication.TenantTokenAuthentication'
    name = 'tenantTokenAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Tenant-specific API token. Format: Token <token>',
        }
