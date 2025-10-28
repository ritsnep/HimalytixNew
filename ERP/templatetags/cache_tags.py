"""
Template tag for fragment caching in Django templates
"""

from django import template
from django.core.cache import cache
from django.utils.encoding import force_str
import hashlib

register = template.Library()


@register.tag
def cache_fragment(parser, token):
    """
    Cache a template fragment with custom key and timeout.
    
    Usage in templates:
        {% load cache_tags %}
        
        {% cache_fragment 300 sidebar request.user.id %}
            ... expensive template logic ...
        {% endcache_fragment %}
        
        {% cache_fragment 600 user_profile user.id user.last_login %}
            ... user profile content ...
        {% endcache_fragment %}
    """
    nodelist = parser.parse(('endcache_fragment',))
    parser.delete_first_token()
    
    # Parse arguments: timeout fragment_name [vary_on...]
    tokens = token.split_contents()
    
    if len(tokens) < 3:
        raise template.TemplateSyntaxError(
            f"'{tokens[0]}' tag requires at least 2 arguments: timeout and fragment_name"
        )
    
    timeout = parser.compile_filter(tokens[1])
    fragment_name = tokens[2]
    vary_on = [parser.compile_filter(token) for token in tokens[3:]]
    
    return CacheFragmentNode(nodelist, timeout, fragment_name, vary_on)


class CacheFragmentNode(template.Node):
    """Node for cache_fragment template tag."""
    
    def __init__(self, nodelist, timeout, fragment_name, vary_on):
        self.nodelist = nodelist
        self.timeout = timeout
        self.fragment_name = fragment_name
        self.vary_on = vary_on
    
    def render(self, context):
        # Resolve timeout
        try:
            timeout = self.timeout.resolve(context)
        except template.VariableDoesNotExist:
            timeout = 300  # Default 5 minutes
        
        # Build cache key
        vary_on_values = [force_str(var.resolve(context)) for var in self.vary_on]
        cache_key = self._make_cache_key(self.fragment_name, vary_on_values)
        
        # Try to get cached content
        cached_content = cache.get(cache_key)
        if cached_content is not None:
            return cached_content
        
        # Render template fragment
        content = self.nodelist.render(context)
        
        # Cache the rendered content
        cache.set(cache_key, content, timeout)
        
        return content
    
    def _make_cache_key(self, fragment_name, vary_on):
        """Build cache key from fragment name and vary_on values."""
        key_parts = ['template_fragment', fragment_name]
        
        if vary_on:
            # Hash vary_on values for shorter keys
            vary_str = ':'.join(vary_on)
            vary_hash = hashlib.md5(vary_str.encode()).hexdigest()[:12]
            key_parts.append(vary_hash)
        
        return ':'.join(key_parts)


@register.simple_tag
def invalidate_fragment(fragment_name, *vary_on):
    """
    Invalidate a cached template fragment.
    
    Usage in templates:
        {% load cache_tags %}
        {% invalidate_fragment 'sidebar' request.user.id %}
    
    Usage in views:
        from django.template.defaulttags import CacheFragmentNode
        # or import from your cache_tags
        
        CacheFragmentNode._make_cache_key('sidebar', [str(user.id)])
        cache.delete(key)
    """
    vary_on_values = [force_str(v) for v in vary_on]
    
    # Build cache key (same logic as CacheFragmentNode)
    key_parts = ['template_fragment', fragment_name]
    
    if vary_on_values:
        vary_str = ':'.join(vary_on_values)
        vary_hash = hashlib.md5(vary_str.encode()).hexdigest()[:12]
        key_parts.append(vary_hash)
    
    cache_key = ':'.join(key_parts)
    
    cache.delete(cache_key)
    return ''  # Return empty string for template rendering


@register.simple_tag(takes_context=True)
def cache_key_for(context, fragment_name, *vary_on):
    """
    Get the cache key for a template fragment (for debugging).
    
    Usage:
        {% cache_key_for 'sidebar' request.user.id as sidebar_key %}
        <!-- Cache key: {{ sidebar_key }} -->
    """
    vary_on_values = [force_str(v) for v in vary_on]
    
    key_parts = ['template_fragment', fragment_name]
    
    if vary_on_values:
        vary_str = ':'.join(vary_on_values)
        vary_hash = hashlib.md5(vary_str.encode()).hexdigest()[:12]
        key_parts.append(vary_hash)
    
    return ':'.join(key_parts)
