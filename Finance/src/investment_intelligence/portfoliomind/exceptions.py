"""Exceptions for the PortfolioMind integration bridge."""


class PortfolioMindBridgeError(Exception):
    """Base exception for PortfolioMind bridge."""


class PortfolioMindConfigurationError(PortfolioMindBridgeError):
    """Bridge is misconfigured or missing credentials."""


class PortfolioMindAuthenticationError(PortfolioMindBridgeError):
    """Authentication to PortfolioMind failed."""


class InstrumentResolutionError(PortfolioMindBridgeError):
    """Failed to resolve Finance asset to PortfolioMind Instrument."""


class InstrumentNotFoundError(InstrumentResolutionError):
    """No matching PortfolioMind Instrument found."""


class AmbiguousInstrumentResolutionError(InstrumentResolutionError):
    """Multiple candidate Instruments matched; safe resolution aborted."""


class PortfolioMindSyncError(PortfolioMindBridgeError):
    """Failed to sync protocol run or state to PortfolioMind."""
