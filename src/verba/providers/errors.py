"""Provider-facing errors. Catch these in the UI layer."""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base error for all provider failures."""


class ProviderNotAvailable(ProviderError):
    """Provider is registered but unusable (missing key, bad endpoint...)."""


class QuotaExceeded(ProviderError):
    """Provider rejected the call due to rate/quota limits."""


class NetworkError(ProviderError):
    """Transport-level failure talking to a remote provider."""
