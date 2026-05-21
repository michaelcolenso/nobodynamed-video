"""Custom exceptions for the nobodynamed video pipeline."""


class SatoriUnavailable(RuntimeError):
    """Raised when the Satori sidecar is unreachable or returns an error."""


class FrameRenderFailed(RuntimeError):
    """Raised when a single frame render fails after all retries."""


class InvalidTier(ValueError):
    """Raised when a name cannot be classified into a known tier."""


class BlocklistedName(ValueError):
    """Raised when a name appears in the editorial blocklist."""


class FfmpegFailed(RuntimeError):
    """Raised when ffmpeg exits with a non-zero status."""


class DataSourceError(RuntimeError):
    """Raised when the data source cannot return a NameRecord."""


class HookResolutionError(RuntimeError):
    """Raised when no compatible editorial hook can be resolved."""
