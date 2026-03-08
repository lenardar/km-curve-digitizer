"""Project-specific exceptions."""


class PyKMExtractError(Exception):
    """Base error for the package."""


class SemanticExtractionError(PyKMExtractError):
    """Semantic extraction failed or returned invalid payload."""


class PixelExtractionError(PyKMExtractError):
    """Pixel extraction failed for one or more curves."""


class BridgeImportError(PyKMExtractError):
    """PyHEOR bridge could not import pyheor."""
