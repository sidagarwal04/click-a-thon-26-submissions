"""ZentraOS ClickHouse adapter.

Two distinct responsibilities that share a driver and nothing else. ``audit``
writes ZentraOS's own metadata-only ledger. ``source_connector`` and
``landing_zone`` read and write customer data for the Connector context, in a
separate database — keeping the ledger's guarantee that it holds no raw
customer values a property of where things live, not of care.
"""

from .audit import AuditEntry, AuditRepository, UnsafeAuditMetadataError
from .cipher import AesGcmCredentialCipher, CredentialSealError
from .landing_zone import UPLOAD_DATABASE, ClickHouseLandingZone
from .source_connector import ClickHouseSourceConnector

__all__ = [
    "UPLOAD_DATABASE",
    "AesGcmCredentialCipher",
    "AuditEntry",
    "AuditRepository",
    "ClickHouseLandingZone",
    "ClickHouseSourceConnector",
    "CredentialSealError",
    "UnsafeAuditMetadataError",
]
