"""
LLM Client with robust error handling, retry logic, and circuit breaker.
Supports Gemini Direct API and OpenRouter with automatic fallback.
"""
import requests
import json
import logging
import base64
import time
import random
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from functools import wraps

from src.config import Config
from src.openrouter_manager import OpenRouterManager

# Google Auth для прямого Gemini API
try:
    from google.auth.transport.requests import Request
    import google.auth
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# RETRY DECORATOR WITH EXPONENTIAL BACKOFF
# ============================================================================

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True


def retry_with_backoff(
    config: RetryConfig = None,
    retryable_exceptions: tuple = (requests.RequestException, TimeoutError),
    retryable_status_codes: tuple = (429, 500, 502, 503, 504)
):
    """
    Decorator that adds retry with exponential backoff to a function.

    Args:
        config: RetryConfig instance
        retryable_exceptions: Exceptions that trigger retry
        retryable_status_codes: HTTP status codes that trigger retry
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    # Check for retryable status code in response
                    if hasattr(result, 'status_code') and result.status_code in retryable_status_codes:
                        raise RetryableError(f"Status code {result.status_code}")

                    return result

                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == config.max_retries:
                        logger.error(f"❌ All {config.max_retries + 1} attempts failed for {func.__name__}")
                        raise

                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )

                    if config.jitter:
                        delay *= (0.5 + random.random())

                    logger.warning(
                        f"⚠️ Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)

            raise last_exception

        return wrapper
    return decorator


class RetryableError(Exception):
    """Exception that triggers retry."""
    pass


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

@dataclass
class CircuitBreakerState:
    """State for circuit breaker."""
    failures: int = 0
    last_failure_time: float = 0.0
    state: str = "closed"  # closed, open, half-open
    success_count: int = 0


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests fail immediately
    - HALF-OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self._state = CircuitBreakerState()

    @property
    def state(self) -> str:
        return self._state.state

    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self._state.state == "closed":
            return True

        if self._state.state == "open":
            # Check if recovery timeout passed
            if time.time() - self._state.last_failure_time >= self.recovery_timeout:
                self._state.state = "half-open"
                self._state.success_count = 0
                logger.info("🔄 Circuit breaker: OPEN → HALF-OPEN (testing recovery)")
                return True
            return False

        if self._state.state == "half-open":
            return True

        return False

    def record_success(self):
        """Record a successful request."""
        if self._state.state == "half-open":
            self._state.success_count += 1
            if self._state.success_count >= self.success_threshold:
                self._state.state = "closed"
                self._state.failures = 0
                logger.info("✅ Circuit breaker: HALF-OPEN → CLOSED (service recovered)")
        elif self._state.state == "closed":
            self._state.failures = 0

    def record_failure(self, error: Exception = None):
        """Record a failed request."""
        self._state.failures += 1
        self._state.last_failure_time = time.time()

        if self._state.state == "half-open":
            self._state.state = "open"
            logger.warning("⚠️ Circuit breaker: HALF-OPEN → OPEN (still failing)")

        elif self._state.state == "closed":
            if self._state.failures >= self.failure_threshold:
                self._state.state = "open"
                logger.error(
                    f"🔴 Circuit breaker: CLOSED → OPEN "
                    f"(failures: {self._state.failures}/{self.failure_threshold})"
                )


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


# ============================================================================
# GEMINI DIRECT CLIENT
# ============================================================================

class GeminiDirectClient:
    """
    Direct client for Google Gemini API via OAuth ADC.
    Includes retry logic and circuit breaker.
    """

    def __init__(self):
        if not GEMINI_AVAILABLE:
            raise ImportError("google-auth not installed. Run: pip install google-auth")

        self.api_base = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model = Config.MODEL_NAME or "gemini-2.0-flash-exp"
        self._access_token = None
        self._token_expiry = 0
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0
        )

    def _get_access_token(self) -> str:
        """Get or refresh OAuth access token."""
        current_time = time.time()

        if not self._access_token or current_time >= self._token_expiry:
            try:
                credentials, _ = google.auth.default(
                    scopes=['https://www.googleapis.com/auth/generative-language.retriever']
                )

                if not credentials.valid:
                    if credentials.expired and credentials.refresh_token:
                        credentials.refresh(Request())

                self._access_token = credentials.token
                self._token_expiry = current_time + 3300  # 55 minutes

            except Exception as e:
                logger.error(f"❌ Gemini Auth Error: {e}")
                raise

        return self._access_token

    def generate(self, system_prompt: str, user_text: str, temperature: float = 0.7) -> str:
        """Regular text generation."""
        return self._execute(system_prompt, user_text, None, None, temperature, False)

    def generate_json(self, system_prompt: str, user_text: str) -> dict:
        """JSON-formatted response."""
        enhanced_prompt = f"{system_prompt}\n\nВАЖНО: Ответ СТРОГО в формате JSON, без markdown разметки."
        res = self._execute(enhanced_prompt, user_text, None, None, 0.1, False)
        try:
            cleaned = res.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON", "raw": res}

    def generate_with_image(self, system_prompt: str, user_text: str, image_base64: str) -> str:
        """Vision request with image."""
        return self._execute(system_prompt, user_text, image_base64, None, 0.5, False)

    def generate_with_audio(self, system_prompt: str, audio_base64: str) -> str:
        """Audio request (Voice Message)."""
        return self._execute(
            system_prompt,
            "Прослушай это аудиосообщение и ответь на него.",
            None, audio_base64, 0.5, False
        )

    @retry_with_backoff(RetryConfig(max_retries=3, base_delay=1.0))
    def _execute(
        self,
        system_prompt: str,
        user_text: str,
        image_base64: Optional[str],
        audio_base64: Optional[str],
        temperature: float,
        json_mode: bool
    ) -> str:
        """Execute request to Gemini API with retry and circuit breaker."""

        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerOpen("Gemini circuit breaker is OPEN")

        try:
            token = self._get_access_token()
            url = f"{self.api_base}/{self.model}:generateContent"

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            parts = [{"text": f"{system_prompt}\n\n{user_text}"}]

            if image_base64:
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_base64
                    }
                })

            if audio_base64:
                parts.append({
                    "inline_data": {
                        "mime_type": "audio/ogg",
                        "data": audio_base64
                    }
                })

            payload = {
                "contents": [{"parts": parts}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": 2048
                }
            }

            response = requests.post(url, json=payload, headers=headers, timeout=45)

            if response.status_code == 200:
                data = response.json()
                if 'candidates' in data and len(data['candidates']) > 0:
                    content = data['candidates'][0]['content']['parts'][0]['text']
                    self.circuit_breaker.record_success()
                    return content
                else:
                    raise ValueError(f"Invalid response format: {data}")
            else:
                self.circuit_breaker.record_failure()
                raise RetryableError(f"Gemini API Error {response.status_code}: {response.text[:200]}")

        except CircuitBreakerOpen:
            raise
        except Exception as e:
            self.circuit_breaker.record_failure(e)
            logger.error(f"❌ Gemini Direct API Error: {e}")
            raise


# ============================================================================
# MAIN CLIENT (Orchestrator)
# ============================================================================

class GeminiClient:
    """
    Main LLM client with automatic provider selection and fallback.

    Modes:
    - auto: Gemini primary → OpenRouter fallback
    - gemini: Only Gemini
    - openrouter: Only OpenRouter
    """

    def __init__(self, provider: str = None):
        if provider is None:
            provider = Config.get_effective_provider()

        self.primary_provider = provider
        self.manager = OpenRouterManager() if Config.OPENROUTER_AVAILABLE else None
        self.or_url = f"{Config.BASE_URL}/chat/completions"

        # Initialize Gemini Direct if available
        self.gemini_direct = None
        if GEMINI_AVAILABLE:
            try:
                self.gemini_direct = GeminiDirectClient()
                if provider == "gemini":
                    logger.info("✅ Gemini Direct API only (no fallback)")
                elif provider == "auto":
                    logger.info("✅ Auto mode: Gemini primary → OpenRouter fallback")
                else:
                    logger.info("✅ OpenRouter primary")
            except Exception as e:
                logger.warning(f"⚠️ Gemini Direct unavailable: {e}")
                if provider == "gemini":
                    raise RuntimeError("Gemini requested but unavailable")

        # Request metrics
        self._request_count = 0
        self._gemini_count = 0
        self._openrouter_count = 0
        self._error_count = 0

    @property
    def stats(self) -> dict:
        """Return request statistics."""
        return {
            "total_requests": self._request_count,
            "gemini_requests": self._gemini_count,
            "openrouter_requests": self._openrouter_count,
            "errors": self._error_count,
            "gemini_circuit_state": self.gemini_direct.circuit_breaker.state if self.gemini_direct else "N/A"
        }

    def generate(self, system_prompt: str, user_text: str, temperature: float = 0.7) -> str:
        """Generate text response."""
        return self._execute(system_prompt, user_text, None, None, temperature, False)

    def generate_json(self, system_prompt: str, user_text: str) -> dict:
        """Generate JSON response."""
        res = self._execute(system_prompt, user_text, None, None, 0.1, True)
        try:
            cleaned = res.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, AttributeError):
            return {"error": "Invalid JSON", "raw": res}

    def generate_with_image(self, system_prompt: str, user_text: str, image_bytes: bytes) -> str:
        """Generate response from image."""
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        return self._execute(system_prompt, user_text, base64_image, None, 0.5, False)

    def generate_with_audio(self, system_prompt: str, audio_bytes: bytes) -> str:
        """Generate response from audio."""
        base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
        return self._execute(system_prompt, "Audio message", None, base64_audio, 0.5, False)

    def _execute(
        self,
        system_prompt: str,
        user_text: str,
        image_base64: Optional[str],
        audio_base64: Optional[str],
        temperature: float,
        json_mode: bool
    ) -> str:
        """Execute request with provider selection and fallback."""
        self._request_count += 1
        start_time = time.time()

        # Auto mode: Try Gemini first, fallback to OpenRouter
        if self.primary_provider == "auto" and self.gemini_direct:
            try:
                logger.info("🔵 Auto mode: Trying Gemini Direct API first...")
                result = self._call_gemini(system_prompt, user_text, image_base64, audio_base64, temperature, json_mode)
                self._gemini_count += 1
                self._log_success("Gemini", start_time)
                return result

            except CircuitBreakerOpen:
                logger.warning("⚠️ Gemini circuit breaker OPEN, using OpenRouter")
            except Exception as e:
                logger.warning(f"⚠️ Gemini failed: {e}")
                logger.info("🔄 Falling back to OpenRouter...")

            # Fallback to OpenRouter
            if self.manager:
                result = self._call_openrouter(system_prompt, user_text, image_base64, temperature, json_mode)
                self._openrouter_count += 1
                self._log_success("OpenRouter (fallback)", start_time)
                return result
            else:
                self._error_count += 1
                raise RuntimeError("Both Gemini and OpenRouter unavailable")

        # Gemini only mode
        elif self.primary_provider == "gemini" and self.gemini_direct:
            result = self._call_gemini(system_prompt, user_text, image_base64, audio_base64, temperature, json_mode)
            self._gemini_count += 1
            self._log_success("Gemini", start_time)
            return result

        # OpenRouter mode
        elif self.manager:
            result = self._call_openrouter(system_prompt, user_text, image_base64, temperature, json_mode)
            self._openrouter_count += 1
            self._log_success("OpenRouter", start_time)
            return result

        else:
            self._error_count += 1
            raise RuntimeError("No LLM provider available")

    def _call_gemini(
        self,
        system_prompt: str,
        user_text: str,
        image_base64: Optional[str],
        audio_base64: Optional[str],
        temperature: float,
        json_mode: bool
    ) -> str:
        """Call Gemini Direct API."""
        if json_mode:
            result = self.gemini_direct.generate_json(system_prompt, user_text)
            return json.dumps(result, ensure_ascii=False)
        elif image_base64:
            return self.gemini_direct.generate_with_image(system_prompt, user_text, image_base64)
        elif audio_base64:
            return self.gemini_direct.generate_with_audio(system_prompt, audio_base64)
        else:
            return self.gemini_direct.generate(system_prompt, user_text, temperature)

    def _call_openrouter(
        self,
        system_prompt: str,
        user_text: str,
        image_base64: Optional[str],
        temperature: float,
        json_mode: bool
    ) -> str:
        """Call OpenRouter API with retry and key rotation."""
        model = self.manager.get_best_free_model()

        user_content = [{"type": "text", "text": user_text}]
        if image_base64:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "provider": {"allow_fallbacks": False}
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        max_retries = 12
        retry_config = RetryConfig(max_retries=3, base_delay=2.0)

        for attempt in range(max_retries):
            headers = self.manager.get_current_headers()
            try:
                response = requests.post(
                    self.or_url,
                    json=payload,
                    headers=headers,
                    timeout=45
                )

                if response.status_code == 200:
                    self.manager.rotate_key()
                    content = response.json()['choices'][0]['message']['content']
                    if not content:
                        raise ValueError("Empty response")
                    return content

                elif response.status_code == 429:
                    logger.warning(f"⚠️ Rate Limit (429). Rotating key...")
                    self.manager.rotate_key()
                    delay = retry_config.base_delay * (retry_config.exponential_base ** (attempt % 4))
                    time.sleep(delay)

                elif response.status_code in [402, 401, 403]:
                    logger.error(f"❌ Key Error ({response.status_code}). Rotating.")
                    self.manager.rotate_key()

                else:
                    logger.warning(f"⚠️ OpenRouter Error {response.status_code}: {response.text[:100]}")
                    self.manager.rotate_key()
                    time.sleep(2)

            except requests.RequestException as e:
                logger.error(f"❌ Network Error: {e}")
                self.manager.rotate_key()
                time.sleep(2)

        self._error_count += 1
        return f"Error: Failed after {max_retries} attempts. Service busy."

    def _log_success(self, provider: str, start_time: float):
        """Log successful request with timing."""
        elapsed = time.time() - start_time
        logger.info(f"✅ {provider} response in {elapsed:.2f}s")
