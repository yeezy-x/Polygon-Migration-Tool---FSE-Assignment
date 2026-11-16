from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Abstract interface for cloud storage providers."""

    @abstractmethod
    def upload_test_case(
        self,
        container_name: str,
        db_problem_id: int,
        test_number: int,
        input_data: str,
        output_data: str,
    ) -> None:
        """Upload a test case's input and output files."""
        raise NotImplementedError

    @abstractmethod
    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: bytes,
    ) -> None:
        """Upload arbitrary binary content."""
        raise NotImplementedError

    @abstractmethod
    def delete_problem_files(
        self,
        container_name: str,
        problem_id: int,
    ) -> None:
        """Delete all files associated with a problem."""
        raise NotImplementedError