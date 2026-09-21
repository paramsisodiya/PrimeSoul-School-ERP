"""
PrimeSoul School ERP - Production Static Files Storage

Resilient Compressed Manifest Static Files Storage extending WhiteNoise.
Ensures full asset compression, cache-busting hashing, and manifest generation,
while gracefully handling unresolvable relative URLs in third-party CSS packages
(e.g., CKEditor, CodeMirror) without crashing collectstatic or raising HTTP 500 on template render.
"""
import logging
from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class ResilientCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    WhiteNoise Compressed Manifest storage that suppresses missing sub-resource
    crashes during CSS URL rewriting and template rendering.
    """
    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content=content, filename=filename)
        except Exception as err:
            logger.warning(
                "Static asset '%s' referenced in CSS could not be hashed by manifest storage: %s. "
                "Retaining unhashed asset reference.",
                name,
                err,
            )
            return name
