import logging
import os
import uuid
from typing import Literal, List
from langgraph.graph import StateGraph, START, END,  MessagesState

from langgraph.types import Command, interrupt
from langchain_core.messages import AIMessage
from langgraph_checkpoint_cosmosdb import CosmosDBSaver
from src.app.services.azure_open_ai import openai_model
from src.app.services.azure_cosmos_db import DATABASE_NAME, chat_container, update_chat_container, patch_active_agent

# Import necessary LCEL components
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage


local_interactive_mode = True # Flag for local development/debugging features

logging.basicConfig(level=logging.ERROR) # Configure basic logging

# Determine the prompts directory relative to the current script
current_script_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_script_dir)
PROMPT_DIR = os.path.join(parent_dir, 'prompts')


# Function to load prompt content from a file
def load_prompt(agent_name):
    """Loads the prompt for a given agent from a file."""
    file_path = os.path.join(PROMPT_DIR, f"{agent_name}.prompty")
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        return ""  # Return empty string if prompt file not found

# Load prompt content for each agent
chart_translator_prompt_content = load_prompt("chart_translator")
health_context_prompt_content = load_prompt("health_context_agent")

# Create ChatPromptTemplate instances using loaded content
chart_translator_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content=chart_translator_prompt_content), # System instruction for the agent
    MessagesPlaceholder(variable_name="messages"), # Placeholder for conversation history
])
health_context_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content=health_context_prompt_content), # System instruction for the agent
    MessagesPlaceholder(variable_name="messages"), # Placeholder for conversation history
])


# Create runnable chains by piping prompts to the LLM
chart_translator = chart_translator_prompt | openai_model
health_context_agent = health_context_prompt | openai_model


# Define graph node functions
def call_chart_translator(state: MessagesState, config) -> Command[Literal["chart_translator", "health_context_agent"]]:
    """Node function for the chart translator agent."""
    sessionId = config["configurable"].get("sessionId", "UNKNOWN_sessionId")
    userId = config["configurable"].get("userId", "UNKNOWN_USER_ID")

    # Retrieve the active agent state from Cosmos DB
    partition_key = [userId, sessionId]
    activeAgent = None
    try:
        activeAgent = chat_container.read_item(
            item=sessionId,
            partition_key=partition_key).get('activeAgent', 'chart_translator') # Default to chart_translator if not found

    except Exception as e:
      # Handle potential DB read errors (logging might be added here)
      pass

    # Initialize chat state in DB if running locally and agent is not set
    if activeAgent is None and local_interactive_mode:
        update_chat_container({
            "id": sessionId,
            "userId": "Victor", # Consider making this dynamic or removing hardcoding
            "sessionId": sessionId,
            "activeAgent": "chart_translator",
            "messages": []
        })
        activeAgent = "chart_translator" # Assume initialization worked

    # Route directly to the correct agent if it's not the chart translator
    if activeAgent is not None and activeAgent not in ["unknown", "chart_translator"]:
        return Command(update=state, goto=activeAgent) # Skip chart translator
    else:
        # Invoke the chart translator chain
        response = chart_translator.invoke(state)

        # Append the AI response to the message history
        ai_message = AIMessage(content=response.content)
        updated_messages = state['messages'] + [ai_message]
        updated_state = {'messages': updated_messages}

        # Transition to the health context agent
        return Command(update=updated_state, goto="health_context_agent")


def call_health_context_agent(state: MessagesState, config) -> Command[Literal["health_context_agent", "human"]]:
    """Node function for the health context agent."""
    sessionId = config["configurable"].get("sessionId", "UNKNOWN_sessionId")
    userId = config["configurable"].get("userId", "UNKNOWN_USER_ID")
    # thread_id = config["configurable"].get("threadId", "UNKNOWN_THREAD_ID") # Unused variable

    # Update active agent in DB if running locally
    if local_interactive_mode:
        patch_active_agent(
            userId="Mark", # Consider making this dynamic or removing hardcoding
            sessionId=sessionId,
            activeAgent="health_context_agent")

    # Invoke the health context agent chain
    response = health_context_agent.invoke(state)

    # Append the AI response to the message history
    ai_message = AIMessage(content=response.content)
    updated_messages = state['messages'] + [ai_message]
    updated_state = {'messages': updated_messages}

    # Transition to the human input node
    return Command(update=updated_state, goto="human")



# Node to pause the graph and wait for user input
def human_node(state: MessagesState, config) -> None:
    """A node for collecting user input."""
    interrupt(value="Ready for user input.") # Signal LangGraph to pause
    return None


# Define the state graph workflow
builder = StateGraph(MessagesState) # Initialize with the message state structure

# Add nodes to the graph
builder.add_node("chart_translator", call_chart_translator)
builder.add_node("health_context_agent", call_health_context_agent)
builder.add_node("human", human_node) # Node for human interaction

# Define the entry point of the graph
builder.add_edge(START, "chart_translator")

# Define transitions between nodes
builder.add_edge("chart_translator", "health_context_agent")
# builder.add_edge("health_context_agent", END) # Changed: Now transitions to human input
builder.add_edge("health_context_agent", "human") # Transition to wait for user input


# Configure the checkpointer for saving graph state to Cosmos DB
checkpointer = CosmosDBSaver(database_name=DATABASE_NAME, container_name="VisualMedQACheckpoints")


# Compile the graph with the checkpointer
visual_med_qa_graph = builder.compile(checkpointer=checkpointer)