"""
Redis Cache Service

Handles all caching operations for financial data with intelligent cache warming,
compression, and monitoring capabilities.

Author: Lebron (Data & Infrastructure Lead)
"""

import asyncio
import json
import logging
import pickle
import zlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
import redis.asyncio as redis
from ..models.financial_data import CacheEntry, DataSource, StockData

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis-based caching service with compression, monitoring, and intelligent cache management.
    """
    
    def __init__(
        self, 
        redis_url: str = "redis://localhost:6379",
        default_ttl: int = 900,  # 15 minutes
        compression_threshold: int = 1024,  # Compress data larger than 1KB
        max_retries: int = 3
    ):
        """
        Initialize cache service.
        
        Args:
            redis_url: Redis connection URL
            default_ttl: Default time-to-live in seconds
            compression_threshold: Compress data larger than this size (bytes)
            max_retries: Maximum retry attempts for Redis operations
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.compression_threshold = compression_threshold
        self.max_retries = max_retries
        self.redis_client = None
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }
        
        # Cache key prefixes for different data types
        self.key_prefixes = {
            'stock_data': 'stock:',
            'company_info': 'company:',
            'financial_statements': 'financials:',
            'market_data': 'market:',
            'search_results': 'search:',
            'api_rate_limits': 'rate_limit:',
            'data_quality': 'quality:'
        }
    
    async def connect(self):
        """Establish Redis connection."""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # We handle encoding ourselves for compression
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Successfully connected to Redis")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")
    
    async def get(self, key: str, data_type: str = 'stock_data') -> Optional[Any]:
        """
        Get data from cache.
        
        Args:
            key: Cache key
            data_type: Type of data for key prefix
            
        Returns:
            Cached data or None if not found/expired
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            full_key = self._build_key(key, data_type)
            
            for attempt in range(self.max_retries):
                try:
                    cached_data = await self.redis_client.get(full_key)
                    
                    if cached_data is None:
                        self.stats['misses'] += 1
                        logger.debug(f"Cache miss for key: {full_key}")
                        return None
                    
                    # Decompress and deserialize
                    data = self._deserialize(cached_data)
                    
                    self.stats['hits'] += 1
                    logger.debug(f"Cache hit for key: {full_key}")
                    return data
                    
                except redis.ConnectionError as e:
                    logger.warning(f"Redis connection error on attempt {attempt + 1}: {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        await self.connect()  # Reconnect
                    else:
                        raise
                        
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        data: Any, 
        ttl: Optional[int] = None, 
        data_type: str = 'stock_data'
    ) -> bool:
        """
        Set data in cache.
        
        Args:
            key: Cache key
            data: Data to cache
            ttl: Time-to-live in seconds (uses default if None)
            data_type: Type of data for key prefix
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            full_key = self._build_key(key, data_type)
            ttl = ttl or self.default_ttl
            
            # Serialize and compress
            serialized_data = self._serialize(data)
            
            for attempt in range(self.max_retries):
                try:
                    await self.redis_client.setex(full_key, ttl, serialized_data)
                    
                    self.stats['sets'] += 1
                    logger.debug(f"Cached data for key: {full_key} (TTL: {ttl}s)")
                    return True
                    
                except redis.ConnectionError as e:
                    logger.warning(f"Redis connection error on attempt {attempt + 1}: {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        await self.connect()  # Reconnect
                    else:
                        raise
                        
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    async def delete(self, key: str, data_type: str = 'stock_data') -> bool:
        """
        Delete data from cache.
        
        Args:
            key: Cache key
            data_type: Type of data for key prefix
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            full_key = self._build_key(key, data_type)
            
            result = await self.redis_client.delete(full_key)
            
            if result:
                self.stats['deletes'] += 1
                logger.debug(f"Deleted cache key: {full_key}")
            
            return bool(result)
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    async def exists(self, key: str, data_type: str = 'stock_data') -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            data_type: Type of data for key prefix
            
        Returns:
            True if key exists, False otherwise
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            full_key = self._build_key(key, data_type)
            result = await self.redis_client.exists(full_key)
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error checking cache key existence {key}: {e}")
            return False
    
    async def get_ttl(self, key: str, data_type: str = 'stock_data') -> Optional[int]:
        """
        Get time-to-live for a cache key.
        
        Args:
            key: Cache key
            data_type: Type of data for key prefix
            
        Returns:
            TTL in seconds or None if key doesn't exist
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            full_key = self._build_key(key, data_type)
            ttl = await self.redis_client.ttl(full_key)
            
            return ttl if ttl > 0 else None
            
        except Exception as e:
            logger.error(f"Error getting TTL for cache key {key}: {e}")
            return None
    
    async def extend_ttl(self, key: str, additional_seconds: int, data_type: str = 'stock_data') -> bool:
        """
        Extend TTL for a cache key.
        
        Args:
            key: Cache key
            additional_seconds: Additional seconds to add to TTL
            data_type: Type of data for key prefix
            
        Returns:
            True if successful, False otherwise
        """
        try:
            current_ttl = await self.get_ttl(key, data_type)
            if current_ttl is None:
                return False
            
            full_key = self._build_key(key, data_type)
            new_ttl = current_ttl + additional_seconds
            
            result = await self.redis_client.expire(full_key, new_ttl)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error extending TTL for cache key {key}: {e}")
            return False
    
    async def get_keys_by_pattern(self, pattern: str, data_type: str = 'stock_data') -> List[str]:
        """
        Get all keys matching a pattern.
        
        Args:
            pattern: Key pattern (supports wildcards)
            data_type: Type of data for key prefix
            
        Returns:
            List of matching keys
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            full_pattern = self._build_key(pattern, data_type)
            keys = await self.redis_client.keys(full_pattern)
            
            # Remove prefix from keys
            prefix = self.key_prefixes[data_type]
            return [key.decode('utf-8').replace(prefix, '') for key in keys]
            
        except Exception as e:
            logger.error(f"Error getting keys by pattern {pattern}: {e}")
            return []
    
    async def clear_expired_keys(self) -> int:
        """
        Clear all expired keys (Redis handles this automatically, but we can force it).
        
        Returns:
            Number of keys cleared
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            # Get all keys and check their TTL
            cleared_count = 0
            
            for data_type in self.key_prefixes.keys():
                pattern = f"{self.key_prefixes[data_type]}*"
                keys = await self.redis_client.keys(pattern)
                
                for key in keys:
                    ttl = await self.redis_client.ttl(key)
                    if ttl == -2:  # Key doesn't exist (expired)
                        cleared_count += 1
            
            logger.info(f"Cleared {cleared_count} expired keys")
            return cleared_count
            
        except Exception as e:
            logger.error(f"Error clearing expired keys: {e}")
            return 0
    
    async def warm_cache(self, symbols: List[str], data_sources: List[DataSource]) -> Dict[str, bool]:
        """
        Warm cache with data for specified symbols.
        
        Args:
            symbols: List of stock symbols
            data_sources: List of data sources to use
            
        Returns:
            Dictionary mapping symbols to success status
        """
        try:
            logger.info(f"Warming cache for {len(symbols)} symbols")
            
            results = {}
            
            # Import here to avoid circular imports
            from .data_service import DataService
            
            data_service = DataService()
            
            for symbol in symbols:
                try:
                    # Get data from primary source
                    stock_data = await data_service.get_stock_data(symbol)
                    
                    if stock_data:
                        # Cache with longer TTL for warmed data
                        success = await self.set(
                            symbol, 
                            stock_data, 
                            ttl=3600,  # 1 hour for warmed cache
                            data_type='stock_data'
                        )
                        results[symbol] = success
                        
                        if success:
                            logger.debug(f"Successfully warmed cache for {symbol}")
                        else:
                            logger.warning(f"Failed to warm cache for {symbol}")
                    else:
                        results[symbol] = False
                        logger.warning(f"No data available to warm cache for {symbol}")
                        
                except Exception as e:
                    logger.error(f"Error warming cache for {symbol}: {e}")
                    results[symbol] = False
                
                # Small delay to avoid overwhelming APIs
                await asyncio.sleep(0.1)
            
            successful = sum(1 for success in results.values() if success)
            logger.info(f"Cache warming completed: {successful}/{len(symbols)} successful")
            
            return results
            
        except Exception as e:
            logger.error(f"Error during cache warming: {e}")
            return {symbol: False for symbol in symbols}
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics and Redis info.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            # Get Redis info
            redis_info = await self.redis_client.info()
            
            # Calculate hit rate
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            # Get memory usage
            memory_used = redis_info.get('used_memory_human', 'Unknown')
            memory_peak = redis_info.get('used_memory_peak_human', 'Unknown')
            
            # Count keys by type
            key_counts = {}
            for data_type, prefix in self.key_prefixes.items():
                pattern = f"{prefix}*"
                keys = await self.redis_client.keys(pattern)
                key_counts[data_type] = len(keys)
            
            return {
                'hit_rate_percent': round(hit_rate, 2),
                'total_hits': self.stats['hits'],
                'total_misses': self.stats['misses'],
                'total_sets': self.stats['sets'],
                'total_deletes': self.stats['deletes'],
                'total_errors': self.stats['errors'],
                'memory_used': memory_used,
                'memory_peak': memory_peak,
                'connected_clients': redis_info.get('connected_clients', 0),
                'key_counts': key_counts,
                'total_keys': sum(key_counts.values()),
                'redis_version': redis_info.get('redis_version', 'Unknown'),
                'uptime_seconds': redis_info.get('uptime_in_seconds', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                'error': str(e),
                'hit_rate_percent': 0,
                'total_hits': self.stats['hits'],
                'total_misses': self.stats['misses'],
                'total_sets': self.stats['sets'],
                'total_deletes': self.stats['deletes'],
                'total_errors': self.stats['errors']
            }
    
    def _build_key(self, key: str, data_type: str) -> str:
        """Build full cache key with prefix."""
        prefix = self.key_prefixes.get(data_type, 'misc:')
        return f"{prefix}{key}"
    
    def _serialize(self, data: Any) -> bytes:
        """
        Serialize and optionally compress data.
        
        Args:
            data: Data to serialize
            
        Returns:
            Serialized (and possibly compressed) bytes
        """
        try:
            # Convert Pydantic models to dict for serialization
            if hasattr(data, 'dict'):
                data = data.dict()
            
            # Serialize to JSON first
            json_data = json.dumps(data, default=str).encode('utf-8')
            
            # Compress if data is large enough
            if len(json_data) > self.compression_threshold:
                compressed_data = zlib.compress(json_data)
                # Add compression flag
                return b'COMPRESSED:' + compressed_data
            else:
                return json_data
                
        except Exception as e:
            logger.error(f"Error serializing data: {e}")
            # Fallback to pickle
            return pickle.dumps(data)
    
    def _deserialize(self, data: bytes) -> Any:
        """
        Deserialize and optionally decompress data.
        
        Args:
            data: Serialized bytes
            
        Returns:
            Deserialized data
        """
        try:
            # Check if data is compressed
            if data.startswith(b'COMPRESSED:'):
                compressed_data = data[11:]  # Remove 'COMPRESSED:' prefix
                json_data = zlib.decompress(compressed_data)
                return json.loads(json_data.decode('utf-8'))
            else:
                # Try JSON first
                try:
                    return json.loads(data.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Fallback to pickle
                    return pickle.loads(data)
                    
        except Exception as e:
            logger.error(f"Error deserializing data: {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Check if Redis is accessible and responsive.
        
        Returns:
            True if Redis is healthy, False otherwise
        """
        try:
            if not self.redis_client:
                await self.connect()
            
            # Test basic operations
            test_key = "health_check_test"
            test_value = {"timestamp": datetime.now().isoformat()}
            
            # Set, get, and delete test data
            await self.set(test_key, test_value, ttl=10, data_type='stock_data')
            retrieved = await self.get(test_key, data_type='stock_data')
            await self.delete(test_key, data_type='stock_data')
            
            return retrieved is not None
            
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return False