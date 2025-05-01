import streamlit as st
from dotenv import load_dotenv
from langchain_azure_dynamic_sessions import SessionsPythonREPLTool

# Load environment variables from .env file
load_dotenv()


# Initialize the SessionsPythonREPLTool for code execution in session pool
try:
    code_interpreter = SessionsPythonREPLTool(
        pool_management_endpoint==st.secrets["POOL_MANAGEMENT_ENDPOINT"], 
        pool_name==st.secrets["AZURE_OPENAI_POOL_NAME"],
        return_direct=True,  # Retorna o resultado diretamente
        include_code=True,   # Inclui o código executado no retorno
        show_tool_use=True   # Mostra explicitamente o uso da ferramenta
    )

except Exception as e:
    # Error initializing SessionsPythonREPLTool
    raise e
