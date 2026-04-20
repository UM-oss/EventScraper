"""
Retry helper z exponential backoff za scraping.
"""

import logging
import time
import random
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)


def retry_with_backoff(
    fn: Callable,
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retriable_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    on_retry: Callable = None,
):
    """
    Pokliči fn() z retry logiko.

    - Ob napaki počakaj base_delay * (backoff_factor ** attempt) sekund.
    - Cap na max_delay.
    - Z jitter=True dodaj naključen 0-50% jitter (preprečuje thundering herd).
    - Vrne (rezultat, attempts_used).
    - Če vsi poskusi failajo, raise zadnjo napako.
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = fn()
            return result, attempt
        except retriable_exceptions as e:
            last_exc = e
            if attempt == max_attempts:
                break
            delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
            if jitter:
                delay += random.uniform(0, delay * 0.5)
            logger.warning(
                f"  Poskus {attempt}/{max_attempts} ni uspel ({type(e).__name__}: {str(e)[:80]}). "
                f"Čakam {delay:.1f}s..."
            )
            if on_retry:
                try:
                    on_retry(attempt, e, delay)
                except Exception:
                    pass
            time.sleep(delay)

    raise last_exc
