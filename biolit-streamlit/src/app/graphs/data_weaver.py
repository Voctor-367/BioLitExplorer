import logging
import os
import uuid
from langchain.schema import BaseMessage, SystemMessage
from langchain_azure_dynamic_sessions import SessionsPythonREPLTool
from typing import Literal
from langgraph.graph import StateGraph, START, MessagesState
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command, interrupt
from langgraph_checkpoint_cosmosdb import CosmosDBSaver
from src.app.services.azure_open_ai import openai_model
from src.app.services.azure_cosmos_db import DATABASE_NAME, update_chat_container
from typing import Literal, List


local_interactive_mode = True

logging.basicConfig(level=logging.ERROR)

# Obter o diretório do script atual (ex: c:\...\src\app\graphs)
current_script_dir = os.path.dirname(__file__)
# Obter o diretório pai (ex: c:\...\src\app)
parent_dir = os.path.dirname(current_script_dir)
# Construir o caminho para o diretório de prompts (ex: c:\...\src\app\prompts)
PROMPT_DIR = os.path.join(parent_dir, 'prompts')



# load prompts
def load_prompt(agent_name):
    """Loads the prompt for a given agent from a file."""
    file_path = os.path.join(PROMPT_DIR, f"{agent_name}.prompty")
    print(f"Loading prompt for {agent_name} from {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Prompt file not found for {agent_name}, using default placeholder.")
        return "You are an AI banking assistant."  # Fallback default prompt

# define agents & tools
code_interpreter = SessionsPythonREPLTool(
    pool_management_endpoint=os.environ["POOL_MANAGEMENT_ENDPOINT"], 
    pool_name=os.environ["AZURE_OPENAI_POOL_NAME"],
    return_direct=True,  # Retorna o resultado diretamente
    include_code=True,   # Inclui o código executado no retorno
    show_tool_use=True   # Mostra explicitamente o uso da ferramenta
)


data_weaver_tools = [
    code_interpreter
]
data_weaver = create_react_agent(
    openai_model,
    tools=data_weaver_tools,
    state_modifier=load_prompt("data_weaver"),
)

# define functions
def call_data_weaver(state: MessagesState, config) -> Command[Literal["data_weaver", "human"]]:
    sessionId = config["configurable"].get("sessionId", "UNKNOWN_sessionId")
    userId = config["configurable"].get("userId", "UNKNOWN_USER_ID")
    study_info = config["configurable"].get("study_info", "UNKNOWN_STUDY_INFO")


    activeAgent = None

     # Get the current messages from the state
    current_messages_list = state.get('messages', [])

    if activeAgent is None:
        if local_interactive_mode:
            # Prepare the message list for the container update
            messages_for_container = []
            if current_messages_list:
                last_message_obj = current_messages_list[-1]
                # Convert the LangChain message object to a dict if needed
                # This assumes a simple structure; adjust if your serialization needs are complex
                if hasattr(last_message_obj, 'to_json'): # Check if it has a standard serialization method
                    messages_for_container.append(last_message_obj.to_json())
                elif isinstance(last_message_obj, BaseMessage): # Basic conversion for BaseMessage
                     messages_for_container.append({
                         "type": last_message_obj.type,
                         "content": last_message_obj.content
                         # Add other relevant fields like 'role' if applicable
                     })
                # Add handling for other potential message types if necessary

            update_chat_container({
                "id": sessionId,
                "userId": userId,
                "sessionId": sessionId,
                "activeAgent": "data_weaver",
                "messages": messages_for_container
            })


    # If active agent is something other than unknown or data_weaver, transfer directly to that agent
    if activeAgent is not None and activeAgent not in ["unknown", "data_weaver"]:
        logging.debug(f"Routing straight to last active agent: {activeAgent}")
        return Command(update=state, goto=activeAgent)
    
    else:
        
        current_messages: List[BaseMessage] = state.get('messages', [])
        messages_for_invoke = list(current_messages)

        if isinstance(study_info, dict) and study_info.get("id") != "UNKNOWN_STUDY_INFO":
            # Format the study context string
            # Assuming study_info is a dictionary with relevant keys
            study_context = f"""Contexto do Estudo Atual:
            - Objetivo: {study_info.get('objective', 'N/A')}
            - Descrição do dataset: {study_info.get('description', 'N/A')}
            - Nome do Dataset: {study_info.get('dataset_name', 'N/A')}
            - Colunas Disponíveis: {study_info.get('columns', 'N/A')}

            Por favor, considere este contexto ao analisar a solicitação."""

            # Create a SystemMessage with the study context
            context_message = SystemMessage(content=study_context)

            # Add the context message to the list of messages
            messages_for_invoke.append(context_message)

        # Create a state dictionary for the invocation
        state_for_invoke = {"messages": messages_for_invoke}

        response = data_weaver.invoke(state_for_invoke)

        return Command(update=response, goto="human")
        
 
        

    

# The human_node with interrupt function serves as a mechanism to stop
# the graph and collect user input for multi-turn conversations.
def human_node(state: MessagesState, config) -> None:
    """A node for collecting user input."""
    interrupt(value="Ready for user input.")
    return None


# define workflow
builder = StateGraph(MessagesState)
builder.add_node("data_weaver", call_data_weaver)
builder.add_node("human", human_node)

builder.add_edge(START, "data_weaver")


# define database to storage chekpoint

checkpointer = CosmosDBSaver(database_name=DATABASE_NAME, container_name="Checkpoints")

# Compile the graph with the checkpointer
graph = builder.compile(checkpointer=checkpointer)

