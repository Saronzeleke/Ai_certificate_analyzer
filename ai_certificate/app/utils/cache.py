import redis.asyncio as redis
from typing import Optional, Any, Dict, List
import json
import logging
from datetime import datetime
import pickle
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache manager for certificate analysis results."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self.client: Optional[redis.Redis] = None
        self.connected: bool = False

    async def connect(self):
        """Connect to Redis."""
        if self.connected:
            return
        try:
            self.client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,
            )
            await self.client.ping()
            self.connected = True
            logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            self.connected = False
            logger.error(f"Failed to connect to Redis: {e}")

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.client and self.connected:
            await self.client.close()
            self.connected = False
            logger.info("Disconnected from Redis")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.connected or not self.client:
            return None
        try:
            data = await self.client.get(key)
            if data is None:
                return None
            # Try JSON first
            try:
                return json.loads(data.decode("utf-8"))
            except Exception:
                return pickle.loads(data)
        except Exception as e:
            logger.error(f"Cache get failed for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache, optionally with TTL."""
        if not self.connected or not self.client:
            return False
        try:
            # Serialize value
            try:
                data = json.dumps(value, default=str).encode("utf-8")
            except Exception:
                data = pickle.dumps(value)

            if ttl:
                await self.client.setex(key, ttl, data)
            else:
                await self.client.set(key, data)
            return True
        except Exception as e:
            logger.error(f"Cache set failed for key {key}: {e}")
            return False

    # Add a proper setex wrapper for legacy code
    async def setex(self, key: str, ttl: int, value: Any) -> bool:
        """Set value with TTL (alias for compatibility)."""
        return await self.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.connected or not self.client:
            return False
        try:
            result = await self.client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete failed for key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.connected or not self.client:
            return False
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists check failed for key {key}: {e}")
            return False

    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern."""
        if not self.connected or not self.client:
            return []
        try:
            return await self.client.keys(pattern)
        except Exception as e:
            logger.error(f"Cache keys failed for pattern {pattern}: {e}")
            return []

    async def clear_pattern(self, pattern: str) -> int:
        """Clear keys matching pattern."""
        if not self.connected or not self.client:
            return 0
        try:
            keys = await self.keys(pattern)
            if keys:
                await self.client.delete(*keys)
                logger.info(f"Cleared {len(keys)} keys matching pattern: {pattern}")
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear pattern failed for {pattern}: {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.connected or not self.client:
            return {"status": "disconnected"}
        try:
            info = await self.client.info()
            analysis_keys = await self.keys("analysis:*")
            certificate_keys = await self.keys("certificate:*")
            return {
                "status": "connected",
                "redis_version": info.get("redis_version", "unknown"),
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "total_analysis_cache": len(analysis_keys),
                "total_certificate_cache": len(certificate_keys),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Cache stats failed: {e}")
            return {"status": "error", "error": str(e)}


# Global cache instance
redis_client = RedisCache()


async def get_redis_client() -> RedisCache:
    """Return global Redis client instance."""
    if not redis_client.connected:
        await redis_client.connect()
    return redis_client


async def init_cache():
    """Initialize cache connection."""
    await redis_client.connect()


async def close_cache():
    """Close cache connection."""
    await redis_client.disconnect()

# import redis.asyncio as redis
# from typing import Optional, Any, Dict
# import json
# import logging
# from datetime import datetime
# import pickle

# from .config import settings

# logger = logging.getLogger(__name__)

# class RedisCache:
#     """Redis cache manager for certificate analysis results"""
    
#     def __init__(self, redis_url: Optional[str] = None):
#         self.redis_url = redis_url or settings.redis_url
#         self.client: Optional[redis.Redis] = None
#         self.connected = False
        
#     async def connect(self):
#         """Connect to Redis"""
#         try:
#             self.client = redis.from_url(
#                 self.redis_url,
#                 encoding="utf-8",
#                 decode_responses=False
#             )
#             await self.client.ping()
#             self.connected = True
#             logger.info(f"Connected to Redis at {self.redis_url}")
#         except Exception as e:
#             logger.error(f"Failed to connect to Redis: {e}")
#             self.connected = False
    
#     async def disconnect(self):
#         """Disconnect from Redis"""
#         if self.client and self.connected:
#             await self.client.close()
#             self.connected = False
#             logger.info("Disconnected from Redis")
    
#     async def get(self, key: str) -> Optional[Any]:
#         """Get value from cache"""
#         if not self.connected or not self.client:
#             return None
        
#         try:
#             data = await self.client.get(key)
#             if data:
#                 try:
#                     # Try JSON first
#                     return json.loads(data.decode('utf-8'))
#                 except:
#                     # Fallback to pickle
#                     return pickle.loads(data)
#             return None
#         except Exception as e:
#             logger.error(f"Cache get failed for key {key}: {e}")
#             return None
    
#     async def set(self, key: str, value: Any, ttl: Optional[int] = None):
#         """Set value in cache"""
#         if not self.connected or not self.client:
#             return False
        
#         try:
#             # Try JSON serialization first
#             try:
#                 data = json.dumps(value, default=str).encode('utf-8')
#             except:
#                 # Fallback to pickle
#                 data = pickle.dumps(value)
            
#             if ttl:
#                 await self.client.setex(key, ttl, data)
#             else:
#                 await self.client.set(key, data)
            
#             return True
#         except Exception as e:
#             logger.error(f"Cache set failed for key {key}: {e}")
#             return False
    
#     async def delete(self, key: str) -> bool:
#         """Delete key from cache"""
#         if not self.connected or not self.client:
#             return False
        
#         try:
#             result = await self.client.delete(key)
#             return result > 0
#         except Exception as e:
#             logger.error(f"Cache delete failed for key {key}: {e}")
#             return False
    
#     async def exists(self, key: str) -> bool:
#         """Check if key exists in cache"""
#         if not self.connected or not self.client:
#             return False
        
#         try:
#             return await self.client.exists(key) > 0
#         except Exception as e:
#             logger.error(f"Cache exists check failed for key {key}: {e}")
#             return False
    
#     async def keys(self, pattern: str = "*") -> list:
#         """Get keys matching pattern"""
#         if not self.connected or not self.client:
#             return []
        
#         try:
#             return await self.client.keys(pattern)
#         except Exception as e:
#             logger.error(f"Cache keys failed for pattern {pattern}: {e}")
#             return []
    
#     async def clear_pattern(self, pattern: str) -> int:
#         """Clear keys matching pattern"""
#         if not self.connected or not self.client:
#             return 0
        
#         try:
#             keys = await self.keys(pattern)
#             if keys:
#                 await self.client.delete(*keys)
#                 logger.info(f"Cleared {len(keys)} keys matching pattern: {pattern}")
#                 return len(keys)
#             return 0
#         except Exception as e:
#             logger.error(f"Cache clear pattern failed for {pattern}: {e}")
#             return 0
    
#     async def get_stats(self) -> Dict[str, Any]:
#         """Get cache statistics"""
#         if not self.connected or not self.client:
#             return {"status": "disconnected"}
        
#         try:
#             info = await self.client.info()
            
#             # Get analysis cache stats
#             analysis_keys = await self.keys("analysis:*")
#             certificate_keys = await self.keys("certificate:*")
            
#             return {
#                 "status": "connected",
#                 "redis_version": info.get("redis_version", "unknown"),
#                 "used_memory": info.get("used_memory_human", "unknown"),
#                 "connected_clients": info.get("connected_clients", 0),
#                 "total_analysis_cache": len(analysis_keys),
#                 "total_certificate_cache": len(certificate_keys),
#                 "timestamp": datetime.now().isoformat()
#             }
#         except Exception as e:
#             logger.error(f"Cache stats failed: {e}")
#             return {"status": "error", "error": str(e)}

# # Global cache instance
# redis_client = RedisCache()

# async def get_redis_client() -> RedisCache:
#     """Get Redis client instance"""
#     if not redis_client.connected:
#         await redis_client.connect()
#     return redis_client

# async def init_cache():
#     """Initialize cache connection"""
#     await redis_client.connect()

# async def close_cache():
#     """Close cache connection"""
#     await redis_client.disconnect()