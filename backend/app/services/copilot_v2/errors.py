"""Exceptions for Copilot V2."""

from typing import Any, Optional


class CodexV2Error(Exception):
    """Base error for all Copilot V2 execution issues."""


class CodexTimeoutError(CodexV2Error):
    """Raised when Codex CLI execution exceeds the configured timeout limit."""

    def __init__(self, message: str, timeout_seconds: float):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds


class CodexAuthError(CodexV2Error):
    """Raised when Codex CLI fails due to missing or invalid authentication/account state."""

    def __init__(self, message: str, raw_details: Optional[str] = None):
        super().__init__(message)
        self.raw_details = raw_details


class CodexCLIExecutionError(CodexV2Error):
    """Raised when the Codex CLI process crashes or exits with a non-zero code."""

    def __init__(self, message: str, returncode: int, stderr: str = "", stdout: str = ""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


class CodexSessionResumeError(CodexCLIExecutionError):
    """Raised when resuming a Codex session fails because the session was not found, expired, or rollout missing."""

    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        returncode: int = 1,
        stderr: str = "",
        stdout: str = "",
    ):
        super().__init__(message=message, returncode=returncode, stderr=stderr, stdout=stdout)
        self.session_id = session_id


class CodexParseError(CodexV2Error):
    """Raised when Codex CLI produces output that cannot be parsed into the expected contract."""

    def __init__(self, message: str, raw_output: str):
        super().__init__(message)
        self.raw_output = raw_output


class ToolExecutionError(CodexV2Error):
    """Raised when tool registry lookup or execution fails."""

    def __init__(self, message: str, tool_name: Optional[str] = None, details: Any = None):
        super().__init__(message)
        self.tool_name = tool_name
        self.details = details
