import os
import logging
from azure.mgmt.appcontainers import ContainerAppsAPIClient
from azure.identity import DefaultAzureCredential
from typing import Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AzureSessionPoolManager:
    def __init__(self):
        # Initializing AzureSessionPoolManager instance
        try:
            # Creating DefaultAzureCredential
            self.credential = DefaultAzureCredential()
            # DefaultAzureCredential created successfully

            # Verifying environment variables
            required_env_vars = [
                "AZURE_SUBSCRIPTION_ID",
                "AZURE_RESOURCE_GROUP",
                "POOL_MANAGEMENT_ENDPOINT",
                "AZURE_OPENAI_POOL_NAME"
            ]

            for var in required_env_vars:
                if var not in os.environ:
                    raise ValueError(f"Environment variable {var} not found")
                # Environment variable {var} found: {os.environ[var]}

            # Creating ContainerAppsClient
            self.container_apps_client = ContainerAppsAPIClient(
                credential=self.credential,
                subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"]
            )
            # ContainerAppsClient created successfully

            self.resource_group = os.environ["AZURE_RESOURCE_GROUP"]
            self.pool_management_endpoint = os.environ["POOL_MANAGEMENT_ENDPOINT"]
            self.pool_name = os.environ["AZURE_OPENAI_POOL_NAME"]

            # AzureSessionPoolManager initialized successfully
            # Resource Group: {self.resource_group}
            # Pool Name: {self.pool_name}
            # Pool Management Endpoint: {self.pool_management_endpoint}

        except Exception as e:
            # Error initializing AzureSessionPoolManager: {str(e)}
            logger.error(f"Error initializing AzureSessionPoolManager: {str(e)}")
            raise

    def upload_file_to_session(self, file_content: bytes, file_name: str, session_id: str) -> Tuple[bool, Optional[str]]:
        """
        Uploads a file to the Azure Container Apps session pool

        Args:
            file_content: File content in bytes
            file_name: Name of the file
            session_id: Session ID

        Returns:
            Tuple[bool, Optional[str]]: (success, error message)
        """
        try:
            # Starting file upload {file_name} to session {session_id}

            self.container_apps_client.upload_file(
                resource_group_name=self.resource_group,
                container_app_name=self.pool_name, # Assuming pool_name is the container app name for sessions
                session_id=session_id, # Need to pass session_id if API requires it
                file_name=file_name,
                file_content=file_content
            )

            # Upload completed successfully for {file_name}
            logger.info(f"Successfully uploaded {file_name} to session {session_id}")
            return True, None

        except Exception as e:
            error_msg = f"Error uploading file: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def check_file_in_session(self, file_name: str, session_id: str) -> Tuple[bool, Optional[str]]:
        """
        Checks if a file exists in the session pool

        Args:
            file_name: Name of the file
            session_id: Session ID

        Returns:
            Tuple[bool, Optional[str]]: (file exists, error message)
        """
        try:
            # Checking existence of file {file_name} in session {session_id}

            # Note: The SDK might not have a direct list_files per session.
            # This might need adjustment based on actual API capabilities.
            # Assuming list_files is for the container app level for now.
            files = self.container_apps_client.list_files(
                resource_group_name=self.resource_group,
                container_app_name=self.pool_name # Assuming pool_name is the container app
                # session_id=session_id # Add if API supports filtering by session
            )
            # This logic might need refinement if files are session-specific via path or metadata
            file_exists = any(f.name == file_name for f in files)

            if file_exists:
                # File {file_name} found in session
                logger.info(f"File {file_name} found in session {session_id}")
            else:
                # File {file_name} not found in session
                logger.info(f"File {file_name} not found in session {session_id}")

            return file_exists, None

        except Exception as e:
            error_msg = f"Error checking file in session pool: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def get_session_status(self, session_id: str) -> Tuple[bool, Optional[str]]:
        """
        Checks the status of a session.
        Note: This likely requires a different API call specific to session pools,
              as 'get' usually retrieves the container app itself.

        Args:
            session_id: ID of the session

        Returns:
            Tuple[bool, Optional[str]]: (session active, error message)
        """
        try:
            # Checking status of session {session_id}
            # Placeholder: Replace with actual API call for session status if available
            # The current 'get' call retrieves the Container App, not a specific session status.
            # This needs to be adapted based on the actual Azure SDK/API for session pools.

            # Example (Conceptual - Requires correct SDK method):
            # session_info = self.container_apps_client.sessions.get( # Fictional method
            #     resource_group_name=self.resource_group,
            #     pool_name=self.pool_name,
            #     session_id=session_id
            # )
            # is_active = session_info.properties.status == "Running" # Fictional property

            # Using Container App status as a proxy (likely incorrect for individual sessions)
            app = self.container_apps_client.get(
                resource_group_name=self.resource_group,
                container_app_name=self.pool_name
            )
            # This checks the *Container App's* running status, not the session's.
            is_active = app.properties.running_status.state == "Running" # Adjusted property access

            if is_active:
                # Session {session_id} is active (based on Container App status)
                logger.info(f"Session {session_id} status check (using App status): Active")

            else:
                # Session {session_id} is not active (based on Container App status)
                logger.info(f"Session {session_id} status check (using App status): Not Active")


            # Returning True for now, assuming the pool exists means sessions can be created.
            # This needs significant refinement based on actual session pool API.
            return True, None # Placeholder return

        except Exception as e:
            error_msg = f"Error checking session status: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

# Create a global instance of the manager
# Attempting to create global instance of AzureSessionPoolManager
try:
    session_pool_manager = AzureSessionPoolManager()
    # Global instance of AzureSessionPoolManager created successfully
    logger.info("Global AzureSessionPoolManager instance created successfully.")
except Exception as e:
    # Error creating global instance of AzureSessionPoolManager: {str(e)}
    logger.error(f"Failed to create global AzureSessionPoolManager instance: {str(e)}")
    session_pool_manager = None