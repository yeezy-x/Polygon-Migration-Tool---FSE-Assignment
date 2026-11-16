import logging

from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient

from .base import StorageProvider

logger = logging.getLogger(__name__)


class AzureStorageProvider(StorageProvider):
    """Azure Blob Storage implementation of StorageProvider."""

    def __init__(
        self,
        account_url: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ):
        self.account_url = account_url

        logger.info("Initializing Azure Blob Storage authentication...")

        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

        self.blob_service_client = BlobServiceClient(
            account_url=self.account_url,
            credential=credential,
        )

        logger.info("Azure BlobServiceClient initialized successfully.")

    def upload_test_case(
        self,
        container_name: str,
        db_problem_id: int,
        test_number: int,
        input_data: str,
        output_data: str,
    ) -> None:
        """Upload input and output files for a test case."""

        input_blob_name = (
            f"test_cases/{db_problem_id}/{test_number:02d}"
        )
        output_blob_name = (
            f"test_cases/{db_problem_id}/{test_number:02d}.a"
        )

        self.upload_blob(
            container_name,
            input_blob_name,
            input_data.encode("utf-8"),
        )

        self.upload_blob(
            container_name,
            output_blob_name,
            output_data.encode("utf-8"),
        )

        logger.info(
            "Uploaded test case #%s for problem %s",
            test_number,
            db_problem_id,
        )

    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: bytes,
    ) -> None:
        """Upload arbitrary content to Azure Blob Storage."""

        blob_client = self.blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name,
        )

        blob_client.upload_blob(
            data,
            overwrite=True,
        )

        logger.info("Uploaded blob: %s", blob_name)

    def delete_problem_files(
        self,
        container_name: str,
        problem_id: int,
    ) -> None:
        """Delete all blobs belonging to a problem."""

        prefix = f"test_cases/{problem_id}/"

        container_client = (
            self.blob_service_client.get_container_client(
                container_name
            )
        )

        blobs_to_delete = [
            blob.name
            for blob in container_client.list_blobs(
                name_starts_with=prefix
            )
        ]

        for blob_name in blobs_to_delete:
            container_client.delete_blob(blob_name)
            logger.info("Deleted blob: %s", blob_name)

        logger.info(
            "Deleted %d blobs for problem %s",
            len(blobs_to_delete),
            problem_id,
        )