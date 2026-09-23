"""Project-specific exceptions."""


class KMDigitizerError(Exception):
    """Base error for the package."""


class SemanticExtractionError(KMDigitizerError):
    """Semantic extraction failed or returned invalid payload."""


class PixelExtractionError(KMDigitizerError):
    """Pixel extraction failed for one or more curves."""
