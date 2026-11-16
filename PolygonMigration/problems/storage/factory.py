import logging

from django.conf import settings

from .azure import AzureStorageProvider
from .base import StorageProvider

logger = logging.getLogger(__name__)


def get_storage_provider(
    account_url: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> StorageProvider:
    """
    Return the configured storage provider.

    Provider selection is controlled by STORAGE_PROVIDER.
    """

    provider = getattr(
        settings,
        "STORAGE_PROVIDER",
        "azure",
    ).lower()

    if provider == "azure":
        logger.info("Initializing Azure storage provider.")

        return AzureStorageProvider(
            account_url=account_url,
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

    raise ValueError(
        f"Unsupported storage provider: {provider}"
    )