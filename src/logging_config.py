"""
Structured JSON Logging Configuration for ConstructionAI System.

Features:
- JSON formatted logs for production (machine-readable)
- Human-readable console logs for development
- Request/Response logging with correlation IDs
- Performance metrics logging
- Error tracking with context
- Log rotation and archival
"""

import os
import sys
import json
import logging
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict, field
from functools import wraps
from pathlib import Path
import time
from contextvars import ContextVar

# Context variable for request correlation
request_id_var: ContextVar[str] = ContextVar('request_id', default='no-request-id')
user_id_var: ContextVar[str] = ContextVar('user_id', default='anonymous')


@dataclass
class LogRecord:
    """Structured log record with all relevant fields."""
    timestamp: str
    level: str
    logger: str
    message: str
    request_id: str = ""
    user_id: str = ""
    duration_ms: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        """Convert to JSON string."""
        data = {k: v for k, v in asdict(self).items() if v is not None and v != "" and v != {}}
        return json.dumps(data, ensure_ascii=False, default=str)


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    Outputs each log record as a single JSON line.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Base log record
        log_record = LogRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            request_id=request_id_var.get(),
            user_id=user_id_var.get()
        )

        # Add extra fields from record
        extra = {}
        for key, value in record.__dict__.items():
            if key not in ('name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'pathname', 'process', 'processName', 'relativeCreated',
                          'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                          'message', 'request_id', 'user_id', 'duration_ms'):
                if value is not None:
                    extra[key] = value

        if extra:
            log_record.extra = extra

        # Add duration if present
        if hasattr(record, 'duration_ms'):
            log_record.duration_ms = record.duration_ms

        # Add error info if exception
        if record.exc_info:
            log_record.error = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "traceback": traceback.format_exception(*record.exc_info) if record.exc_info[0] else []
            }

        return log_record.to_json()


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable console formatter with colors.
    """

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        # Add color
        color = self.COLORS.get(record.levelname, '')

        # Format timestamp
        timestamp = datetime.now().strftime('%H:%M:%S')

        # Build message
        prefix = f"{color}[{timestamp}] [{record.levelname:>8}]{self.RESET}"

        # Add request ID if present
        req_id = request_id_var.get()
        if req_id != 'no-request-id':
            prefix += f" [{req_id[:8]}]"

        message = f"{prefix} {record.name}: {record.getMessage()}"

        # Add duration if present
        if hasattr(record, 'duration_ms'):
            message += f" ({record.duration_ms:.2f}ms)"

        # Add exception info
        if record.exc_info:
            message += f"\n{traceback.format_exception(*record.exc_info)[-1].strip()}"

        return message


def setup_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: Optional[str] = None,
    log_dir: str = "logs"
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Use JSON format for console output
        log_file: Optional file path for logging
        log_dir: Directory for log files

    Returns:
        Root logger instance
    """
    # Create log directory if needed
    if log_file or log_dir:
        Path(log_dir).mkdir(exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    if json_output:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ConsoleFormatter())

    root_logger.addHandler(console_handler)

    # File handler (always JSON for machine parsing)
    if log_file:
        file_path = Path(log_dir) / log_file
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


# ═══════════════════════════════════════════════════════════════
# CONTEXT MANAGERS AND DECORATORS
# ═══════════════════════════════════════════════════════════════

def set_request_context(request_id: Optional[str] = None, user_id: Optional[str] = None):
    """Set context variables for the current request."""
    if request_id:
        request_id_var.set(request_id)
    else:
        request_id_var.set(str(uuid.uuid4()))

    if user_id:
        user_id_var.set(user_id)


def clear_request_context():
    """Clear context variables."""
    request_id_var.set('no-request-id')
    user_id_var.set('anonymous')


class RequestContext:
    """Context manager for request-scoped logging."""

    def __init__(self, request_id: Optional[str] = None, user_id: Optional[str] = None):
        self.request_id = request_id or str(uuid.uuid4())
        self.user_id = user_id or 'anonymous'
        self._token_req = None
        self._token_user = None

    def __enter__(self):
        self._token_req = request_id_var.set(self.request_id)
        self._token_user = user_id_var.set(self.user_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        request_id_var.reset(self._token_req)
        user_id_var.reset(self._token_user)
        return False


def log_execution_time(logger: logging.Logger = None, level: int = logging.INFO):
    """
    Decorator to log function execution time.

    Usage:
        @log_execution_time()
        def my_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)

            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Create log record with duration
                logger.log(
                    level,
                    f"{func.__name__} completed",
                    extra={'duration_ms': duration_ms, 'function': func.__name__}
                )
                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"{func.__name__} failed: {str(e)}",
                    extra={'duration_ms': duration_ms, 'function': func.__name__},
                    exc_info=True
                )
                raise

        return wrapper
    return decorator


def log_async_execution_time(logger: logging.Logger = None, level: int = logging.INFO):
    """
    Decorator to log async function execution time.

    Usage:
        @log_async_execution_time()
        async def my_async_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)

            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                logger.log(
                    level,
                    f"{func.__name__} completed",
                    extra={'duration_ms': duration_ms, 'function': func.__name__}
                )
                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"{func.__name__} failed: {str(e)}",
                    extra={'duration_ms': duration_ms, 'function': func.__name__},
                    exc_info=True
                )
                raise

        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════
# SPECIALIZED LOGGERS
# ═══════════════════════════════════════════════════════════════

class LLMLogger:
    """
    Specialized logger for LLM requests and responses.
    Tracks tokens, latency, costs, and errors.
    """

    def __init__(self, name: str = "llm"):
        self.logger = logging.getLogger(f"constructionai.{name}")
        self._request_count = 0
        self._total_tokens = 0
        self._total_latency_ms = 0

    def log_request(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        provider: str = "gemini",
        success: bool = True,
        error: Optional[str] = None
    ):
        """Log an LLM request with metrics."""
        self._request_count += 1
        if success:
            self._total_tokens += prompt_tokens + completion_tokens
            self._total_latency_ms += latency_ms

        extra = {
            'event_type': 'llm_request',
            'model': model,
            'provider': provider,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': prompt_tokens + completion_tokens,
            'latency_ms': latency_ms,
            'success': success,
            'request_number': self._request_count
        }

        if error:
            extra['error'] = error
            self.logger.error(f"LLM request failed: {error}", extra=extra)
        else:
            self.logger.info(f"LLM request completed ({model})", extra=extra)

    def get_stats(self) -> Dict:
        """Get aggregated statistics."""
        return {
            'total_requests': self._request_count,
            'total_tokens': self._total_tokens,
            'avg_latency_ms': self._total_latency_ms / max(self._request_count, 1),
            'total_latency_ms': self._total_latency_ms
        }


class BotLogger:
    """
    Specialized logger for Telegram bot events.
    """

    def __init__(self):
        self.logger = logging.getLogger("constructionai.bot")

    def log_message(
        self,
        user_id: int,
        chat_id: int,
        message_type: str,
        text: Optional[str] = None,
        intent: Optional[str] = None,
        agent: Optional[str] = None
    ):
        """Log incoming message."""
        extra = {
            'event_type': 'bot_message',
            'user_id': user_id,
            'chat_id': chat_id,
            'message_type': message_type
        }

        if intent:
            extra['intent'] = intent
        if agent:
            extra['agent'] = agent
        if text:
            extra['text_preview'] = text[:100] + '...' if len(text) > 100 else text

        self.logger.info(f"Message from user {user_id}", extra=extra)

    def log_response(
        self,
        user_id: int,
        chat_id: int,
        response_type: str,
        latency_ms: float,
        agent: str
    ):
        """Log bot response."""
        extra = {
            'event_type': 'bot_response',
            'user_id': user_id,
            'chat_id': chat_id,
            'response_type': response_type,
            'latency_ms': latency_ms,
            'agent': agent
        }

        self.logger.info(f"Response sent to user {user_id}", extra=extra)

    def log_error(
        self,
        user_id: int,
        error: Exception,
        context: str = ""
    ):
        """Log bot error."""
        extra = {
            'event_type': 'bot_error',
            'user_id': user_id,
            'error_type': type(error).__name__,
            'context': context
        }

        self.logger.error(f"Error for user {user_id}: {str(error)}", extra=extra, exc_info=True)


class RAGLogger:
    """
    Specialized logger for RAG operations.
    """

    def __init__(self):
        self.logger = logging.getLogger("constructionai.rag")

    def log_search(
        self,
        query: str,
        method: str,
        num_results: int,
        top_score: float,
        latency_ms: float
    ):
        """Log RAG search operation."""
        extra = {
            'event_type': 'rag_search',
            'method': method,
            'num_results': num_results,
            'top_score': round(top_score, 4),
            'latency_ms': latency_ms,
            'query_length': len(query)
        }

        self.logger.info(f"RAG search completed ({method})", extra=extra)


# ═══════════════════════════════════════════════════════════════
# SINGLETON INSTANCES
# ═══════════════════════════════════════════════════════════════

# Global logger instances
_llm_logger: Optional[LLMLogger] = None
_bot_logger: Optional[BotLogger] = None
_rag_logger: Optional[RAGLogger] = None


def get_llm_logger() -> LLMLogger:
    """Get or create the LLM logger singleton."""
    global _llm_logger
    if _llm_logger is None:
        _llm_logger = LLMLogger()
    return _llm_logger


def get_bot_logger() -> BotLogger:
    """Get or create the bot logger singleton."""
    global _bot_logger
    if _bot_logger is None:
        _bot_logger = BotLogger()
    return _bot_logger


def get_rag_logger() -> RAGLogger:
    """Get or create the RAG logger singleton."""
    global _rag_logger
    if _rag_logger is None:
        _rag_logger = RAGLogger()
    return _rag_logger


# ═══════════════════════════════════════════════════════════════
# QUICK SETUP
# ═══════════════════════════════════════════════════════════════

def configure_for_production():
    """Configure logging for production environment."""
    setup_logging(
        level="INFO",
        json_output=True,
        log_file=f"constructionai_{datetime.now().strftime('%Y%m%d')}.log",
        log_dir="logs"
    )


def configure_for_development():
    """Configure logging for development environment."""
    setup_logging(
        level="DEBUG",
        json_output=False,
        log_file=None
    )


# ═══════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════

def run_logging_test():
    """Test logging configuration."""
    print("=" * 60)
    print("Logging Configuration Test")
    print("=" * 60)

    # Test development mode
    print("\n--- Development Mode (Human Readable) ---")
    configure_for_development()

    logger = get_logger("test")

    with RequestContext(user_id="user123"):
        logger.debug("This is a debug message")
        logger.info("This is an info message")
        logger.warning("This is a warning")

        # Test LLM logger
        llm_logger = get_llm_logger()
        llm_logger.log_request(
            model="gemini-2.0-flash",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=234.5,
            provider="gemini"
        )

        # Test bot logger
        bot_logger = get_bot_logger()
        bot_logger.log_message(
            user_id=12345,
            chat_id=12345,
            message_type="text",
            text="Нужен гипсокартон",
            intent="sales"
        )

        # Test RAG logger
        rag_logger = get_rag_logger()
        rag_logger.log_search(
            query="доставка",
            method="hybrid",
            num_results=3,
            top_score=0.85,
            latency_ms=12.3
        )

    # Test JSON mode
    print("\n--- Production Mode (JSON) ---")
    configure_for_production()

    logger2 = get_logger("test.json")
    with RequestContext(request_id="req-12345", user_id="user456"):
        logger2.info("JSON formatted log message")

    print("\n" + "=" * 60)
    print("Logging test completed!")


if __name__ == "__main__":
    run_logging_test()
