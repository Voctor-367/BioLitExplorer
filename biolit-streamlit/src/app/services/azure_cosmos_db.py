import logging
import os
from datetime import datetime
import base64
import json
from azure.cosmos import exceptions
from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.ERROR)

# Azure Cosmos DB configuration
COSMOS_DB_URL = os.getenv("COSMOSDB_ENDPOINT")
DATABASE_NAME = "biolit"

cosmos_client = None
database = None
container = None

# Define Cosmos DB containers
chat_container = None
debug_container = None
chat_history_container = None
users_container = None


try:
    credential = DefaultAzureCredential()
    token = credential.get_token("https://management.azure.com/.default")

    cosmos_client = CosmosClient(COSMOS_DB_URL, credential=credential)
    # Connected to Cosmos DB successfully using DefaultAzureCredential.
    
except Exception as dac_error:
    # Failed to authenticate using DefaultAzureCredential
    raise dac_error

# Initialize Cosmos DB client and containers
try:
    database = cosmos_client.get_database_client(DATABASE_NAME)
    # Connected to Cosmos DB: {DATABASE_NAME}

    chat_container = database.get_container_client("Chat")
    checkpoint_container = database.get_container_client("Checkpoints")
    checkpoint_visual_med_qa = database.get_container_client("VisualMedQACheckpoints")
    chat_history_container = database.get_container_client("ChatHistory")
    studies_container = database.get_container_client("Studies")
    users_container = database.get_container_client("Users")
    debug_container = database.get_container_client("Debug")

    # All Cosmos containers connected

except Exception as e:
    # Error initializing Cosmos DB Containers
    raise e


# update the user data container
def update_chat_container(data):
    try:
        chat_container.upsert_item(data)
        logging.debug(f"User data saved to Cosmos DB: {data}")
    except Exception as e:
        # Error saving user data to Cosmos DB
        raise e

# update the user data container
def update_studies_container(data):
    try:
        studies_container.upsert_item(data)
        # New study saved to Cosmos DB
    except Exception as e:
        # Error saving user data to Cosmos DB
        raise e

# fetch the study data from the container by studyId (document id) when sessionId is the partition key
def fetch_study_by_id(study_id: str):
    """
    Fetches study data from the Studies container based on the study ID (document ID)
    using a cross-partition query because sessionId is the partition key.

    Args:
        study_id: The unique ID of the study document.

    Returns:
        A dictionary containing the study data, or None if not found.
    """
    try:
        # Fetching study data via query for study_id
        query = "SELECT * FROM c WHERE c.id = @study_id"
        parameters = [{"name": "@study_id", "value": study_id}]

        # Must enable cross-partition query as the filter is on 'id', not the partition key 'sessionId'
        items = list(studies_container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))

        if items:
            # Fetched study data successfully for study_id
            # Assuming study_id is unique, return the first item found.
            return items[0]
        else:
            # No study data found for study_id
            return None
    except exceptions.CosmosHttpResponseError as e:
        # Handle potential HTTP errors during query
        # Cosmos DB HTTP error querying study data for study_id
        return None
    except Exception as e:
        # Unexpected error querying study data for study_id
        return None


def update_users_container(data):
    try:
        users_container.upsert_item(data)
        # Users data saved to Cosmos DB
    except Exception as e:
        # Error saving Users data to Cosmos DB
        raise e


# fetch the user data from the container by tenantId, userId
def fetch_chat_container_by_user(userId):
    try:
        query = f"SELECT * FROM c WHERE c.userId = '{userId}'"
        items = list(chat_container.query_items(query=query, enable_cross_partition_query=True))
        # Fetched user data count for userId
        return items
    except Exception as e:
        # Error fetching user data for userId
        raise e

'''
# fetch the user data from the container by tenantId, userId, sessionId
def fetch_chat_container_by_session(userId, sessionId):
    try:
        query = f"SELECT * FROM c WHERE c.userId = '{userId}' AND c.sessionId = '{sessionId}'"
        items = list(chat_container.query_items(query=query, enable_cross_partition_query=True))
        # Fetched user data count for tenantId, userId, sessionId
        return items
    except Exception as e:
        # Error fetching user data for tenantId, userId, sessionId
        raise e
'''

# patch the active agent in the user data container using patch operation
def patch_active_agent(userId, sessionId, activeAgent):
    try:
        operations = [
            {'op': 'replace', 'path': '/activeAgent', 'value': activeAgent}
        ]

        try:
            pk = [userId, sessionId]
            chat_container.patch_item(item=sessionId, partition_key=pk,
                                      patch_operations=operations)
        except Exception as e:
            # Error occurred during patch operation
            pass # Consider logging the error message e.message
    except Exception as e:
        # Error patching active agent for tenantId, userId, sessionId
        raise e

    # deletes the user data from the container by tenantId, userId, sessionId



'''
def update_active_agent_in_latest_message(sessionId: str, new_active_agent: str):
    try:
        # Fetch the latest message from the ChatHistory container
        query = f"SELECT * FROM c WHERE c.sessionId = '{sessionId}' ORDER BY c._ts DESC OFFSET 0 LIMIT 1"
        items = list(chat_history_container.query_items(query=query, enable_cross_partition_query=True))

        if not items:
            # No chat history found for sessionId
            return

        latest_message = items[0]
        latest_message['sender'] = new_active_agent

        # Upsert the updated message back into the ChatHistory container
        chat_history_container.upsert_item(latest_message)
        # Updated activeAgent in the latest message for sessionId

    except Exception as e:
        # Error updating activeAgent in the latest message for sessionId
        raise e
'''