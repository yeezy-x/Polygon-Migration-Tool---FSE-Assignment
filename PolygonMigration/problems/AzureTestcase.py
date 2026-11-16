import logging

from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)


class AzureBlobManager:
    """
    A manager class to handle read/write operations for Azure Blob Storage.

    Provides methods to upload and delete test cases as blobs.
    """

    def __init__(self, account_url, tenant_id, client_id, client_secret):
        self.account_url = account_url
        self.blob_service_client = None

        logger.info("Initializing Azure Blob Storage authentication...")

        try:
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )

            self.blob_service_client = BlobServiceClient(
                account_url=self.account_url,
                credential=credential
            )

            logger.info("Azure BlobServiceClient initialized successfully.")

        except Exception:
            logger.exception("Azure authentication initialization failed.")
            raise

    def upload_test_case(
        self,
        container_name,
        db_problem_id,
        test_number,
        input_data,
        output_data
    ):
        """
        Uploads a test case's input and output as separate blobs.
        """

        input_blob_name = f"test_cases/{db_problem_id}/{test_number:02d}"
        output_blob_name = f"test_cases/{db_problem_id}/{test_number:02d}.a"

        try:
            input_blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=input_blob_name
            )

            input_blob_client.upload_blob(
                input_data.encode("utf-8"),
                overwrite=True
            )

            logger.info(
                f"Uploaded input for test #{test_number} to {input_blob_name}"
            )

            output_blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=output_blob_name
            )

            output_blob_client.upload_blob(
                output_data.encode("utf-8"),
                overwrite=True
            )

            logger.info(
                f"Uploaded output for test #{test_number} to {output_blob_name}"
            )

        except Exception as e:
            logger.error(f"Error uploading test case #{test_number}: {e}")

    def empty_blob(self, container_name, problem_id):
        """
        Deletes all blobs for a given database problem ID.
        """

        prefix = f"test_cases/{problem_id}/"

        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )

            blobs_to_delete = [
                blob.name
                for blob in container_client.list_blobs(
                    name_starts_with=prefix
                )
            ]

            for blob_name in blobs_to_delete:
                logger.info(f"Deleting blob: {blob_name}")
                container_client.delete_blob(blob_name)

            logger.info(
                f"Deleted {len(blobs_to_delete)} blobs for problem "
                f"{problem_id} in container {container_name}."
            )

        except Exception as e:
            logger.error(
                f"Error deleting blobs for problem {problem_id}: {e}"
            )