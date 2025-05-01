import streamlit as st
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from langchain_openai import AzureChatOpenAI
from openai import AzureOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings



# Use DefaultAzureCredential to get a token
def get_azure_ad_token():
    try:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://cognitiveservices.azure.com/.default")

        print(f"[DEBUG] Retrieved Azure AD token successfully using DefaultAzureCredential: {token.token}")
    except Exception as e:
        print(f"[ERROR] Failed to retrieve Azure AD token: {e}")
        raise e
    return token.token

# Fetch AD Token
azure_ad_token = get_azure_ad_token()
 
try:
    azure_openai_api_version = "2024-12-01-preview"
    azure_deployment_name = model=st.secrets("AZURE_OPENAI_COMPLETIONSDEPLOYMENTID")
    openai_model = AzureChatOpenAI(
        azure_deployment=azure_deployment_name,
        api_version=azure_openai_api_version,
        temperature=0,
        azure_ad_token=azure_ad_token
    )
    aoai_client = AzureOpenAI(
        azure_ad_token=azure_ad_token,
        api_version="2024-12-01-preview",
        azure_endpoint=st.secrets("AZURE_OPENAI_ENDPOINT")
    )
    print("[DEBUG] Azure OpenAI model initialized successfully.")
except Exception as e:
    print(f"[ERROR] Error initializing Azure OpenAI model: {e}")
    raise e
