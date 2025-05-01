import streamlit as st
# Import the SYNCHRONOUS client
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient # Synchronous client

# Load environment variables

# --- Authentication ---
try:
     # Attempting authentication using DefaultAzureCredential.
     credential = DefaultAzureCredential()
     # DefaultAzureCredential initialized successfully.
except Exception as e:
     # Error obtaining Azure credential with DefaultAzureCredential
     credential = None # Ensure credential is None on failure


# --- Blob Storage Client (SYNCHRONOUS) ---
STORAGE_ACCOUNT_URL=st.secrets["AZURE_STORAGE_ACCOUNT_URL"]
STORAGE_CONTAINER_NAME=st.secrets["AZURE_STORAGE_CONTAINER_NAME"] # Default container name

blob_service_client_sync = None # Initialize sync client variable

if not STORAGE_ACCOUNT_URL:
    # Error: AZURE_STORAGE_ACCOUNT_URL environment variable not set.
    pass # Handle missing URL appropriately
elif credential:
    try:
        # Initialize the SYNCHRONOUS client
        blob_service_client_sync = BlobServiceClient(account_url=STORAGE_ACCOUNT_URL, credential=credential)
        # SYNC BlobServiceClient initialized for account
    except Exception as e:
        # Error initializing SYNC BlobServiceClient
        pass # Handle initialization error
else:
    # Credential not obtained, cannot initialize BlobServiceClient.
    pass # Handle missing credential


# --- Synchronous Upload Function ---
def upload_blob_sync(file_contents: bytes, blob_name: str): # Synchronous function definition
    """Uploads bytes to a specific blob (synchronous version)."""
    if not blob_service_client_sync:
        raise ConnectionError("SYNC Blob Service Client not initialized.")
    if not STORAGE_CONTAINER_NAME:
         raise ValueError("Storage container name is not configured.")

    try:
        # Get the SYNCHRONOUS blob client
        blob_client = blob_service_client_sync.get_blob_client(
            container=STORAGE_CONTAINER_NAME,
            blob=blob_name
        )
        # Call the SYNCHRONOUS upload method (no await)
        blob_client.upload_blob(file_contents, overwrite=True) # Overwrite if blob exists
        # Successfully uploaded blob (sync)
        return blob_client.url # Return the URL of the uploaded blob
    except Exception as e:
        # Error uploading blob (sync)
        raise # Re-raise the exception after logging (or handling)
