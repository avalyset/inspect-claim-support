# Single import surface that Inspect loads via the setuptools entry point.
# Importing the scorer here registers it (through the @scorer decorator) so it
# is resolvable by name once the package is installed.
from .scorers import claim_support

__all__ = ["claim_support"]
