"""Exceptions of the data layer."""


class DataError(Exception):
    """A request failed or returned unusable data."""


class DataUnavailable(DataError):
    """A data source is not configured or not available (use the next fallback)."""
