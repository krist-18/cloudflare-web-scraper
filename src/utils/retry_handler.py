from __future__ import annotations

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

def retry_policy(max_attempts: int = 3):
    """
    Build a tenacity retry decorator with sane defaults:
    - exponential backoff starting at 1s up to ~10s
    - retry only on Exceptions (can be narrowed by callers)
    """
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
    )