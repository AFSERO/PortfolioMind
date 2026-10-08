"""Model profile abstraction for Copilot V2.

Maps logical tiers (FAST, BALANCED, DEEP) to verified Codex CLI models,
default reasoning effort, default tool budget, and timeout budgets.
"""

from dataclasses import dataclass
from enum import Enum
import os
from typing import Optional


class ModelProfile(str, Enum):
    """Logical model tiers for Copilot V2.

    Explicitly locked to FAST, BALANCED, DEEP.
    No intermediate or composite variants (e.g. FAST+, ULTRA) are permitted.
    """

    FAST = "FAST"
    BALANCED = "BALANCED"
    DEEP = "DEEP"


class ReasoningEffort(str, Enum):
    """Reasoning effort values supported natively by the installed Codex CLI.

    Verified options: low, medium, high, xhigh.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


@dataclass(frozen=True)
class ProfileConfig:
    """Runtime configuration for a single logical model profile."""

    profile: ModelProfile
    model_name: str
    default_reasoning_effort: ReasoningEffort
    default_tool_budget: int
    timeout_seconds: float


# Default verified models from Codex CLI inspection (with env var overrides)
# Verified working on local Codex CLI 0.154.0 with ChatGPT account tier:
# - FAST: gpt-5.6-luna (fast and efficient model for simpler tasks)
# - BALANCED: gpt-5.6-terra (balanced model for straightforward work)
# - DEEP: gpt-6-astra (frontier intelligence for demanding reasoning)
_DEFAULT_PROFILE_MAP = {
    ModelProfile.FAST: {
        "env_model_key": "CODEX_V2_FAST_MODEL",
        "default_model": "gpt-5.6-luna",
        "default_effort": ReasoningEffort.LOW,
        "default_budget": 3,
        "timeout": 45.0,
    },
    ModelProfile.BALANCED: {
        "env_model_key": "CODEX_V2_BALANCED_MODEL",
        "default_model": "gpt-5.6-terra",
        "default_effort": ReasoningEffort.MEDIUM,
        "default_budget": 6,
        "timeout": 90.0,
    },
    ModelProfile.DEEP: {
        "env_model_key": "CODEX_V2_DEEP_MODEL",
        "default_model": "gpt-6-astra",
        "default_effort": ReasoningEffort.HIGH,
        "default_budget": 12,
        "timeout": 180.0,
    },
}


def get_profile_config(
    profile: ModelProfile | str,
    reasoning_effort_override: Optional[ReasoningEffort | str] = None,
) -> ProfileConfig:
    """Resolve the active ProfileConfig for a logical ModelProfile.

    Reasoning effort can be overridden independently at runtime.
    Raises ValueError on unknown profile or reasoning effort values.
    """
    if isinstance(profile, str):
        try:
            profile = ModelProfile(profile.strip().upper())
        except ValueError:
            raise ValueError(f"Unknown ModelProfile: '{profile}'. Must be FAST, BALANCED, or DEEP.")

    meta = _DEFAULT_PROFILE_MAP[profile]
    model_name = os.environ.get(meta["env_model_key"], meta["default_model"])

    effective_effort = meta["default_effort"]
    if reasoning_effort_override is not None:
        if isinstance(reasoning_effort_override, str):
            try:
                effective_effort = ReasoningEffort(reasoning_effort_override.strip().lower())
            except ValueError:
                raise ValueError(
                    f"Unsupported reasoning effort '{reasoning_effort_override}'. "
                    f"Allowed: {[e.value for e in ReasoningEffort]}"
                )
        else:
            effective_effort = reasoning_effort_override

    return ProfileConfig(
        profile=profile,
        model_name=model_name,
        default_reasoning_effort=effective_effort,
        default_tool_budget=meta["default_budget"],
        timeout_seconds=meta["timeout"],
    )
