"""
Integration tests for caching
"""
import pytest
from django.core.cache import cache
from utils.caching import cache_key, cache_result, invalidate_cache


@pytest.mark.integration
class TestCaching:
    """Test suite for caching utilities."""
    
    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()
    
    def test_cache_key_generation(self):
        """
        Test that cache keys are generated consistently.
        """
        key1 = cache_key('user', user_id=123, tenant='acme')
        key2 = cache_key('user', user_id=123, tenant='acme')
        
        assert key1 == key2
        assert 'himalytix' in key1
        assert '123' in key1
        assert 'acme' in key1
    
    def test_cache_result_decorator(self):
        """
        Test that @cache_result decorator caches function results.
        """
        call_count = 0
        
        @cache_result(timeout=60, key_prefix='test')
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call - executes function
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call - returns cached result
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Not called again
        
        # Different args - executes function
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2
    
    def test_cache_set_and_get(self):
        """
        Test basic cache set and get operations.
        """
        key = cache_key('test', item='data')
        cache.set(key, {'foo': 'bar'}, 60)
        
        result = cache.get(key)
        assert result == {'foo': 'bar'}
    
    def test_cache_expiration(self):
        """
        Test that cache entries expire after timeout.
        """
        import time
        
        key = cache_key('test', item='expire')
        cache.set(key, 'value', 1)  # 1 second timeout
        
        # Immediately available
        assert cache.get(key) == 'value'
        
        # Wait for expiration
        time.sleep(2)
        assert cache.get(key) is None
    
    def test_cache_delete(self):
        """
        Test cache deletion.
        """
        key = cache_key('test', item='delete')
        cache.set(key, 'value', 60)
        
        assert cache.get(key) == 'value'
        
        cache.delete(key)
        assert cache.get(key) is None
    
    def test_cache_many(self):
        """
        Test setting and getting multiple cache entries.
        """
        data = {
            cache_key('test', item=1): 'value1',
            cache_key('test', item=2): 'value2',
            cache_key('test', item=3): 'value3',
        }
        
        cache.set_many(data, 60)
        
        result = cache.get_many(data.keys())
        assert len(result) == 3
        assert result[cache_key('test', item=1)] == 'value1'
