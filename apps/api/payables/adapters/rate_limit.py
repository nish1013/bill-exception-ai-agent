import logging
import time
import uuid
from functools import cache
from uuid import UUID

import redis
from django.conf import settings

from payables.domain.proposals.proposals import REQUESTS_PER_MINUTE

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60


class RedisProposalRateLimiter:
    """Allows 5 proposal requests per tenant in any 60 s (D30). A refused request also counts."""

    def __init__(self, client: redis.Redis | None = None) -> None:
        self._client = client or _shared_client()

    def allow(self, tenant_id: UUID) -> bool:
        key = f"{settings.RATE_LIMIT_PREFIX}:proposal-requests:{tenant_id}"
        now = time.time()
        try:
            pipeline = self._client.pipeline()
            pipeline.zremrangebyscore(key, 0, now - WINDOW_SECONDS)
            pipeline.zadd(key, {uuid.uuid4().hex: now})
            pipeline.zcard(key)
            pipeline.expire(key, WINDOW_SECONDS)
            count = pipeline.execute()[2]
        except redis.RedisError:
            # A Redis loss resets the rate limit, never the quota (D30, architecture: storage).
            logger.warning("rate limit not read, request allowed", exc_info=True)
            return True
        return count <= REQUESTS_PER_MINUTE


@cache
def _shared_client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1)
