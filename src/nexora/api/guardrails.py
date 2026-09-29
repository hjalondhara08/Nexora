"""
Nexora Guardrails Module
========================
Provides input and output guardrails to ensure safety,
defend against prompt injection, and prevent secret leakage.
"""

import re
from typing import Optional
from nexora.api.models import GuardrailValidationResult

# Regex patterns for prompt injection & system jailbreak attempts
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|prompts|rules)",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|prompts|rules)",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"enable\s+dan\s+mode",
    r"bypass\s+all\s+(safety|content)\s+filters",
    r"reveal\s+(your\s+)?(system\s+prompt|initial\s+instructions|master\s+prompt)",
    r"print\s+(your\s+)?(system\s+prompt|hidden\s+prompt)",
    r"<\s*script\s*>",
    r"javascript\s*:",
    r"exec\s*\(\s*['\"]",
]

# Destructive commands to block
DESTRUCTIVE_COMMANDS = [
    r"\brm\s+-rf\s+/",
    r"\bmkfs\b",
    r"\bdd\s+if=/dev/zero",
    r"\b:\(\)\{\s*:\|:&\s*\};:",  # Fork bomb
    r"\bDROP\s+DATABASE\b",
    r"\bDROP\s+TABLE\b",
]

# Secret / API key patterns to redact from outputs
SECRET_PATTERNS = [
    (r"gsk_[a-zA-Z0-9]{30,}", "[REDACTED_GROQ_KEY]"),
    (r"sk-[a-zA-Z0-9]{32,}", "[REDACTED_API_KEY]"),
    (r"tvly-[a-zA-Z0-9]{20,}", "[REDACTED_TAVILY_KEY]"),
    (r"hf_[a-zA-Z0-9]{30,}", "[REDACTED_HF_TOKEN]"),
    (r"postgresql://[^:]+:[^@]+@", "postgresql://[REDACTED_USER]:[REDACTED_PASS]@"),
]


def validate_input(user_prompt: str) -> GuardrailValidationResult:
    """
    Validates user input against safety guidelines and injection patterns.
    """
    if not user_prompt or not user_prompt.strip():
        return GuardrailValidationResult(
            passed=False,
            category="empty_input",
            reason="Input message cannot be empty.",
        )

    # Check for excessive length (DoS / context flood)
    if len(user_prompt) > 8000:
        return GuardrailValidationResult(
            passed=False,
            category="length_exceeded",
            reason="Input message exceeds maximum allowed limit of 8000 characters.",
        )

    # Check prompt injection patterns
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, user_prompt, re.IGNORECASE):
            return GuardrailValidationResult(
                passed=False,
                category="prompt_injection",
                reason="Input contains restricted prompt injection or system override instructions.",
            )

    # Check destructive commands
    for pattern in DESTRUCTIVE_COMMANDS:
        if re.search(pattern, user_prompt, re.IGNORECASE):
            return GuardrailValidationResult(
                passed=False,
                category="malicious_command",
                reason="Input contains potentially destructive command patterns.",
            )

    return GuardrailValidationResult(
        passed=True,
        sanitized_content=user_prompt.strip(),
    )


def apply_output_guardrails(response_text: str) -> str:
    """
    Sanitizes assistant output by masking any inadvertently leaked API keys or credentials.
    """
    if not response_text:
        return ""

    sanitized = response_text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized
