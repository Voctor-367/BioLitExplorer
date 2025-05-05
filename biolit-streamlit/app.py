import streamlit as st
import pandas as pd
import uuid
import streamlit_modal as modal
from src.app.tools.data_weaver_tools import code_interpreter
from src.app.services.azure_cosmos_db import update_studies_container # Assuming this exists
from src.app.graphs.visual_med_qa import visual_med_qa_graph # Visual QA graph
from src.app.graphs.data_weaver import graph # Data analysis graph
from src.app.services.search_pubmed import search_pmc_articles
from src.app.services.azure_blob import upload_blob_sync
from langchain.schema import AIMessage, HumanMessage # Import message types
from langchain.schema.messages import ToolMessage
import base64
from datetime import datetime, timedelta # Import time utilities
from PIL import Image
import io
import copy
import json
import time # Added for simulating delays


# Set page configuration
st.set_page_config(page_title="BioLit Analysis", layout="wide")

# Custom CSS for styling
st.markdown("""
<style>
    /* Sidebar study item styling */
    .study-item {
        background-color: white;
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 10px;
        border: 1px solid #E2E8F0;
        border-left: 3px solid #38B2AC; /* Default color, can be changed based on status */
    }
    .study-item-title {
        font-weight: 600;
        font-size: 14px;
        margin-bottom: 3px;
    }
    .study-item-details {
        color: #718096;
        font-size: 12px;
    }
    /* Style for the setup form container */
   .setup-form-container {
        background-color: white;
        padding: 20px; /* Space inside the container */
        border-radius: 10px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);

        /* --- Responsive Width Configuration --- */
        width: 100%; /* Attempt to fill parent container width */
        max-width: 960px; /* Maximum width constraint for larger screens - adjust as needed */
        margin-left: auto; /* Center the container horizontally */
        margin-right: auto; /* Center the container horizontally */

        /* --- Height Configuration --- */
        /* Let the content determine the height */

        /* Optional: Add some margin above/below the container itself */
        margin-top: 20px;
        margin-bottom: 20px;
    }

    .setup-form-container h3 {
        margin-top: 0;
        color: #1A202C;
        font-weight: 600;
    }

    /* Center the form submit button */
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {
        background-color: #2D7FF9; /* Blue color */
        border: none;
    }
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] {
        display: flex;
        justify-content: center;
    }

    /* --- Custom Modal Size --- */
    .st-modal-container {
        max-width: 80% !important; /* Example: Set max width to 80% of viewport */
        width: 900px !important;   /* Example: Or set a fixed width */
    }

</style>
""", unsafe_allow_html=True)


# --- Initialize Session State ---
# Initialize chat messages for data analysis
if "messages" not in st.session_state:
    st.session_state.messages = []
# Initialize chat messages for literature search
if "literature_messages" not in st.session_state:
    st.session_state.literature_messages = []
# Initialize thread ID for graph state
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
# Initialize session ID for user session tracking
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
# Initialize study information dictionary
if "study_info" not in st.session_state:
    st.session_state.study_info = {}
# Flag indicating if a CSV has been uploaded
if "csv_uploaded" not in st.session_state:
    st.session_state.csv_uploaded = False
# Flag to control showing the chat interface vs. setup
if "show_chat" not in st.session_state:
    st.session_state.show_chat = False
# State to hold the image for modal view
if "image_to_view" not in st.session_state:
    st.session_state.image_to_view = None
# State to hold the index of the image being viewed
if "image_to_view_index" not in st.session_state:
    st.session_state.image_to_view_index = None
# State to track which message index is requesting explanation (-1 = none)
if "requesting_explanation_index" not in st.session_state:
    st.session_state.requesting_explanation_index = -1
# State to store the path of the last uploaded blob
if "last_uploaded_blob" not in st.session_state:
    st.session_state.last_uploaded_blob = None

# Initialize study history with example data
if "study_history" not in st.session_state:
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    last_week = now - timedelta(days=7)

    st.session_state.study_history = [
        {
            "id": str(uuid.uuid4()),
            "title": "Efficacy of Drug Alpha vs. Placebo for Arterial Hypertension",
            "objective": "To evaluate the reduction in systolic blood pressure with Drug Alpha compared to placebo after 12 weeks of treatment.",
            "description": "Dataset from a randomized, double-blind, Phase III clinical trial, including demographic data, baseline and follow-up blood pressure, and serious adverse events.",
            "dataset_name": "clinical_trial_drug_alpha_htn_phase3_anon.csv",
            "columns": "ParticipantID, TreatmentGroup, Age, Sex, BaselineSystolicBP, Week12SystolicBP, SeriousAdverseEvents",
            "created_at": last_week.isoformat() + "Z"
        },
         {
        "id": str(uuid.uuid4()),
        "title": "Risk Factors for Type 2 Diabetes Mellitus in an Urban Population",
        "objective": "To identify the main risk factors (lifestyle, family history, biochemical markers) associated with the development of T2DM.",
        "description": "Data from a prospective cohort study following 5,000 adults for 10 years, collecting annual data on habits, laboratory tests, and diagnoses.",
        "dataset_name": "cohort_t2dm_risk_urban_10yr_followup.parquet",
        "columns": "IndividualID, BaselineAge, BaselineBMI, PhysicalActivity_hrs_week, MediterraneanDietScore, FamilyHistoryDM2, FastingGlucoseYear0, FastingGlucoseYear10, T2DMDiagnosis_10years",
        "created_at": yesterday.isoformat() + "Z"
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Survival Analysis Post-Pediatric Heart Transplantation",
        "objective": "To assess the 1-year, 5-year, and 10-year survival rates and identify prognostic factors in children undergoing heart transplantation.",
        "description": "Retrospective multicenter data from pediatric patients (<18 years) who received a heart transplant between 2000 and 2020.",
        "dataset_name": "survival_ped_heart_tx_multicenter_2000_2020.xlsx",
        "columns": "PatientRegistry, TransplantDate, TransplantAge_months, CauseOfHeartFailure, DonorType, WaitingTime_days, AcuteRejectionYear1, FollowUpTime_years, VitalStatus",
        "created_at": last_week.isoformat() + "Z"
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Impact of Early Physical Therapy on Recovery After Ischemic Stroke",
        "objective": "To compare functional recovery (modified Rankin Scale) at 6 months between patients who started physical therapy <48h vs. >48h after ischemic stroke.",
        "description": "Observational study comparing two groups of patients admitted with acute ischemic stroke to a rehabilitation center.",
        "dataset_name": "early_physio_stroke_rankin_6m.csv",
        "columns": "PatientID, TimeToPhysioStart_hours, Age, Admission_NIHSS, StrokeLocation, ComorbidityIndex, mRS_6months",
        "created_at": yesterday.isoformat() + "Z"
    }
    ]
    # Initialized study history with example studies.


# --- Helper Function to Reset for New Study ---
def reset_for_new_study():
    """Resets session state variables to start a new study setup."""
    st.session_state.messages = []
    st.session_state.literature_messages = []
    st.session_state.study_info = {}
    st.session_state.csv_uploaded = False
    st.session_state.show_chat = False
    st.session_state.image_to_view = None
    st.session_state.image_to_view_index = None
    st.session_state.requesting_explanation_index = -1
    st.session_state.last_uploaded_blob = None
    # Session state reset for new study.


# --- Setup Interface Function ---
def show_setup_interface():
    """Displays the interface for setting up a new study."""
    # Use columns to center the setup form
    setup_col_left, setup_col_main, setup_col_right = st.columns([1,2,1])
    with setup_col_main:
        st.title("New Study")
        st.write("Fill in the study information and upload your CSV file.")

        # --- Dataset Uploader ---
        st.subheader("1. Upload Dataset")
        uploaded_file = st.file_uploader(
            "Choose CSV file",
            type=['csv'],
            accept_multiple_files=False,
            key="csv_uploader_setup",
            label_visibility="collapsed",
            help="Upload the CSV file containing the data for analysis."
        )

        # --- Data Preview ---
        df_head = None
        if uploaded_file is not None:
            try:
                # Attempt to read CSV head with different separators
                try:
                    df_head = pd.read_csv(uploaded_file, nrows=5, sep=',')
                except Exception:
                    uploaded_file.seek(0) # Reset file pointer
                    try:
                        df_head = pd.read_csv(uploaded_file, nrows=5, sep=';')
                    except Exception:
                         uploaded_file.seek(0) # Reset file pointer
                         df_head = pd.read_csv(uploaded_file, nrows=5)

                st.write("Data Preview (first 5 rows):")
                st.dataframe(df_head, use_container_width=True)
                uploaded_file.seek(0) # Reset pointer after reading head
            except Exception as e:
                st.error(f"Error previewing CSV file: {e}")
                df_head = None # Ensure df_head is None if preview fails

        # --- Study Details Form ---
        st.subheader("2. Study Details")
        with st.form("setup_form"):
            study_title = st.text_input(
                "Study Title",
                key="setup_title",
                help="Give a descriptive name to your study."
            )
            study_objective = st.text_area(
                "Study Objective",
                key="setup_objective",
                height=100,
                help="What is the main scientific question or objective you want to investigate with this specific analysis? Be as clear as possible about what you hope to discover or compare.\n\n Examples: **'Identify differentially expressed genes between group A and B'**, **'See if treatment X improves outcome Y compared to placebo'**, **'Find protein biomarkers that correlate with disease severity Z'**, **'Build a predictive model for recurrence risk'**. A well-defined objective guides the AI ​​to perform the most appropriate statistical analyses and visualizations, as well as better direct the literature search."
            )
            description = st.text_area(
                "Describe your dataset",
                key="setup_description",
                height=100,
                help="Help the AI ​​agent understand your data for more accurate analysis! Briefly describe the origin and content of the dataset. Include:\n\n **1) Study Type/Design** (e.g. ‘RNA-Seq comparing Treated vs Control’, ‘Clinical trial demographics and outcomes’, ‘Proteomics of diseased vs healthy tissue’)\n\n **2) Key Columns/Variables** you are likely to analyze (e.g. ‘gene expression levels’, ‘treatment group’, ‘survival status’, ‘protein abundance’, specific names of important columns).\n\n **3) Any crucial biological/experimental context**.\n\n This information will guide the AI ​​in formulating relevant analyses and interpreting the results."
            )
            # Form submission button
            submitted = st.form_submit_button("Start Analysis")

        if submitted:
            # --- Input Validations ---
            error_messages = []
            if not study_title: error_messages.append("Study Title is required.")
            if not study_objective: error_messages.append("Study Objective is required.")
            if not description: error_messages.append("Dataset description is required.")
            if uploaded_file is None:
                error_messages.append("Please select a CSV file.")
            # elif df_head is None and uploaded_file is not None: # Check if preview failed
            #     error_messages.append("Error processing CSV file. Check format.")

            if error_messages:
                for msg in error_messages:
                    st.error(msg)
            else:
                # --- Process Setup ---
                with st.spinner("Setting up environment and processing data..."):
                    try:
                        # Read file content and name
                        uploaded_file.seek(0)
                        file_contents = uploaded_file.getvalue()
                        dataset_name = uploaded_file.name
                        try:
                            # Read full DataFrame to get columns
                            try:
                                df = pd.read_csv(io.BytesIO(file_contents), sep=',')
                            except Exception:
                                file_contents.seek(0) # Reset buffer pointer
                                try:
                                     df = pd.read_csv(io.BytesIO(file_contents), sep=';')
                                except Exception:
                                     file_contents.seek(0) # Reset buffer pointer
                                     df = pd.read_csv(io.BytesIO(file_contents))

                            dataset_columns = list(df.columns)
                            columns_str = ", ".join(dataset_columns)
                            # CSV processed: dataset_name, Columns: columns_str
                        except Exception as e:
                            # Error reading CSV with Pandas to get columns
                            st.error(f"Error processing CSV columns: {e}. Check file format.")
                            st.stop() # Stop if columns can't be read

                        # Generate IDs and timestamp
                        study_id = str(uuid.uuid4())
                        session_id = st.session_state.session_id
                        created_at = datetime.utcnow().isoformat() + "Z"

                        # Prepare study info dictionaries
                        study_info_for_session = {
                            "id": study_id,
                            "title": study_title,
                            "objective": study_objective,
                            "description": description,
                            "dataset_name": dataset_name,
                            "columns": columns_str,
                            "created_at": created_at
                        }
                        # Study Info for Session State: study_info_for_session

                        study_info_for_cosmos = copy.deepcopy(study_info_for_session)
                        study_info_for_cosmos["sessionId"] = session_id
                        study_info_for_cosmos["userId"] = "Victor" # Placeholder user ID
                        # study_info_for_cosmos["createdAt"] = created_at # Already included

                        # Save study metadata to Cosmos DB
                        try:
                            update_studies_container(study_info_for_cosmos)
                            # Study study_id saved initially to Cosmos DB.
                        except Exception as e:
                            # Error saving study to Cosmos DB
                            st.error("Error saving study information to the database.")
                            st.stop()

                        # Upload dataset to Azure Blob Storage
                        blob_name = f"uploads/{session_id}/{dataset_name}"
                        try:
                            uploaded_file.seek(0) # Ensure pointer is at start
                            blob_url = upload_blob_sync(uploaded_file.getvalue(), blob_name)
                            # Upload to Blob Storage complete: blob_url
                            st.session_state.last_uploaded_blob = blob_name
                        except Exception as e:
                            # Error uploading to Blob Storage
                            st.error("Error sending file to storage.")
                            st.stop() # Stop if blob upload fails

                        # Upload dataset to Code Interpreter Session Pool
                        try:
                            uploaded_file.seek(0) # Ensure pointer is at start
                            metadata = code_interpreter.upload_file(
                                data=uploaded_file.getvalue(),
                                remote_file_path=dataset_name
                            )
                            # Upload to Session Pool complete: metadata
                            # Optionally update Cosmos with pool path if needed
                            # pool_file_path = metadata.get('path_on_compute')
                            # if pool_file_path:
                            #    study_info_for_cosmos["pool_file_path"] = pool_file_path
                            #    try:
                            #        update_studies_container(study_info_for_cosmos)
                            #        # Study study_id updated in Cosmos DB with pool_file_path.
                            #    except Exception as e_update:
                            #        # Error UPDATING study in Cosmos DB with pool path
                        except Exception as e:
                            # Error uploading to Session Pool
                            st.error("Error preparing code analysis environment.")
                            st.stop() # Stop if pool upload fails

                        # --- Update Session State ---
                        st.session_state.study_info = study_info_for_session
                        st.session_state.csv_uploaded = True
                        st.session_state.show_chat = True

                        # Add new study to history for sidebar display
                        st.session_state.study_history.append(study_info_for_session)
                        # Added new study 'study_title' to history.

                        st.success("Environment configured successfully! Redirecting to chat...")
                        time.sleep(0.5) # Short delay before rerun
                        st.rerun()

                    except Exception as e:
                        # Unexpected error during setup
                        st.error(f"An unexpected error occurred during setup: {e}")


# --- Process Graph Update Function ---
def process_update(update):
    """Processes updates streamed from the LangGraph graph."""
    for node_id, value in update.items():
        # Processing update from node node_id: value
        if isinstance(value, dict) and value.get("messages"):
            last_message = value["messages"][-1]
            # Processing update from node node_id for storage: last_message

            # Handle AI messages (non-tool calls)
            if isinstance(last_message, AIMessage):
                if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
                    st.session_state.messages.append({"role": "assistant", "content": last_message.content})
                    # Stored AIMessage: last_message.content[:50]...

            # Handle Tool messages (specifically Python REPL)
            elif isinstance(last_message, ToolMessage) and last_message.name == 'Python_REPL':
                # Check for preceding AI message with tool call details (agent thought process)
                if len(value["messages"]) > 1:
                    penult_message = value["messages"][-2]
                    if isinstance(penult_message, AIMessage) and hasattr(penult_message, 'tool_calls') and penult_message.tool_calls:
                        # Store the agent's thought process message
                        st.session_state.messages.append({"role": "assistant", "content": penult_message.content})
                        # Stored Agent Thought: penult_message.content[:50]...
                        try:
                            # Extract and store the Python code executed
                            tool_call = penult_message.tool_calls[0]
                            if tool_call['name'] == 'Python_REPL':
                                python_code = tool_call['args'].get("python_code", "")
                                st.session_state.messages.append({
                                    "role": "assistant", "content": python_code, "expander": True # Mark for expander display
                                })
                                # Stored Python Code for expander.
                        except Exception as e:
                            # Error extracting Python code from tool_call
                            pass
                try:
                    # Process the result of the tool execution (stdout, stderr, artifacts)
                    result = json.loads(last_message.content)
                    if result.get('stdout'):
                        # Store standard output
                        st.session_state.messages.append({"content": result['stdout']})
                        # Stored stdout: result['stdout'][:50]...

                    if result.get('stderr'):
                        # Store standard error, formatted for display
                        stderr_message = f"❌ Error:\n```\n{result['stderr']}\n```"
                        st.session_state.messages.append({"error": stderr_message, "expander": True}) # Mark for expander
                        # Stored stderr for expander.

                    # Check for artifacts (e.g., images) attached to the ToolMessage
                    if hasattr(last_message, 'artifact') and last_message.artifact:
                        artifact = last_message.artifact

                        if isinstance(artifact, dict) and artifact.get('result'):
                            result_data = artifact['result']

                            # Handle image artifacts
                            if result_data.get('type') == 'image' and result_data.get('base64_data'):
                                image_data = base64.b64decode(result_data['base64_data'])
                                st.session_state.messages.append({
                                    "image": image_data # Store image bytes
                                })
                                # Stored Image.
                except json.JSONDecodeError:
                    # Error decoding tool result JSON.
                    pass
                except Exception as e:
                    # Unexpected error processing ToolMessage
                    pass

        st.rerun() # Rerun Streamlit to update the UI with the new message


# --- Data Analysis Chat Interface Function ---
def show_chat_interface(container=st):
    """Displays the main chat interface for data analysis."""
    with container:
        # Verify study information is loaded
        if not st.session_state.get("study_info") or not st.session_state.study_info.get("id"):
             st.error("Error: Study information not loaded.")
             st.stop()

        # Define session configuration for graph calls
        session_config = {
            "configurable": {
                "thread_id": st.session_state.thread_id,
                "sessionId": st.session_state.session_id,
                "userId": "Victor", # Placeholder user ID
                "study_info": st.session_state.study_info, # Pass study info
            }
        }

        st.subheader(f"Analysis: {st.session_state.study_info.get('title', 'Untitled')} 🔬")

        # --- Instantiate Modals ---
        image_viewer_modal = modal.Modal(key="image_viewer_modal_instance", title="")

        # --- Chat Message Display Loop ---
        chat_container_analysis = st.container(height=650) # Container with fixed height for scrolling
        with chat_container_analysis:

            st.info("Use the chat below to start your analysis") # Initial message

            for index, message in enumerate(st.session_state.messages):
                # Determine message role for display (default to assistant)
                role = message.get("role", "assistant")

                with st.chat_message(role):
                    if message.get("expander"):
                        # Display messages marked for expander (code or errors)
                        if "error" in message:
                            # Display error messages in an expander
                            with st.expander("Execution Error"):
                                st.error(message.get("error", "Unknown error"))
                        elif "content" in message:
                            # Display Python code in an expander
                            with st.expander("Executed Python Code"):
                                st.code(message.get("content", ""), language="python")

                    elif "image" in message:
                        # Display image messages
                        st.image(message["image"]) # Display the image bytes
                        # Buttons below the image
                        col1_img, col2_img, col3_img = st.columns([1,1,1])
                        with col1_img:
                            # Button to open image viewer modal
                            if st.button("View Chart", key=f"view_button_{index}"):
                                st.session_state.image_to_view = message["image"]
                                st.session_state.image_to_view_index = index
                                image_viewer_modal.open()
                        with col2_img:
                            # Button to download the image
                            st.download_button(
                                label="Download Chart", data=message["image"],
                                file_name=f"chart_{index}.png", mime="image/png",
                                key=f"download_button_{index}"
                            )
                        with col3_img:
                            # Button to request explanation for this image
                            if st.button("Request Explanation", key=f"explanation_button_{index}"):
                                # Set the index for which explanation is requested
                                st.session_state.requesting_explanation_index = index
                                st.rerun() # Rerun to show the explanation input container

                        # --- Conditional Explanation Input Container ---
                        # Show this container only if explanation is requested for this specific message index
                        if st.session_state.requesting_explanation_index == index:
                            with st.container(border=True): # Add border for visual separation
                                explanation_question = st.text_area(
                                    "Enter your question about this chart:",
                                    key=f"explanation_input_{index}"
                                )
                                # Button to submit the explanation question
                                if st.button("Send Question", key=f"explanation_send_{index}"):
                                    if explanation_question.strip():
                                        # Get the corresponding image bytes
                                        image_bytes = message.get("image")
                                        if not image_bytes:
                                            st.error("Error: Could not find the image associated with this question.")
                                        else:
                                            # 1. Add user's question to message history
                                            st.session_state.messages.append({
                                                "role": "user",
                                                "content": f"Question about the previous chart: {explanation_question}"
                                            })
                                            # 2. Reset explanation index to hide the input container
                                            st.session_state.requesting_explanation_index = -1

                                            # --- Prepare Multimodal Input for Visual QA Graph ---
                                            try:
                                                # Encode image to Base64 Data URL
                                                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                                                data_url = f"data:image/png;base64,{base64_image}" # Assuming PNG format

                                                # Image converted to base64

                                                # Construct the multimodal message content
                                                multimodal_content = [
                                                    {"type": "text", "text": explanation_question},
                                                    {
                                                        "type": "image_url",
                                                        "image_url": {"url": data_url}
                                                    }
                                                ]
                                                # Create a HumanMessage with the multimodal content
                                                multimodal_input_message = HumanMessage(content=multimodal_content)

                                                # Prepare input dictionary for the graph
                                                input_for_graph = {"messages": [multimodal_input_message]}

                                                # 3. Invoke the Visual Medical QA graph
                                                with st.spinner("Analyzing the question about the chart..."):
                                                    # Invoking visual_med_qa_graph with multimodal input and config
                                                    # Use the same session_config for consistency
                                                    final_state = visual_med_qa_graph.invoke(input_for_graph, config=session_config)

                                                    # Final state of the visual graph: final_state

                                                    # 4. Process the response from the visual QA graph
                                                    if final_state and final_state.get("messages"):
                                                        # Assuming the response is in the last messages
                                                        # Extract chart translator response (if exists)
                                                        if len(final_state["messages"]) > 1:
                                                            explanation_chart_translator = final_state["messages"][-2]
                                                            if isinstance(explanation_chart_translator, AIMessage):
                                                                st.session_state.messages.append({
                                                                    "role": "assistant",
                                                                    "content": explanation_chart_translator.content
                                                                })

                                                        # Extract health context agent response
                                                        explanation_health_context = final_state["messages"][-1]
                                                        if isinstance(explanation_health_context, AIMessage):
                                                            st.session_state.messages.append({
                                                                "role": "assistant",
                                                                "content": explanation_health_context.content
                                                            })
                                                        else:
                                                            # Unexpected response from visual_med_qa_graph
                                                            st.session_state.messages.append({
                                                                "role": "assistant",
                                                                "content": "Could not get a formatted explanation."
                                                            })
                                                    else:
                                                        st.session_state.messages.append({
                                                            "role": "assistant",
                                                            "content": "No response from the explanation assistant."
                                                        })

                                            except Exception as e:
                                                # Error preparing input or invoking visual_med_qa_graph
                                                st.error(f"An error occurred while trying to get the explanation: {e}")
                                                # Add error message to chat history
                                                st.session_state.messages.append({
                                                    "role": "assistant",
                                                    "content": f"Error processing the question about the chart: {e}"
                                                })

                                            # 5. Rerun to display the question and the response/error
                                            st.rerun()
                                    else:
                                        st.warning("Please enter your question before sending.")
                    else:
                        # Display standard text messages
                        st.write(message["content"])

            # --- Image Viewer Modal Definition ---
            if image_viewer_modal.is_open():
                with image_viewer_modal.container():
                    if st.session_state.image_to_view:
                        # Display the selected image in the modal
                        st.image(st.session_state.image_to_view, use_column_width=True)
                        # Add download button inside the modal
                        st.download_button(
                            label="Download Chart",
                            data=st.session_state.image_to_view,
                            file_name=f"chart_{st.session_state.study_info.get('id', 'study')}_{st.session_state.image_to_view_index}_enlarged.png",
                            mime="image/png",
                            key=f"download_button_modal_{st.session_state.image_to_view_index}"
                        )

        # --- Data Analysis Chat Input ---
        if prompt := st.chat_input("Enter your message"):
            # Add user message to history
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Prepare input for the data analysis graph
            input_message = {"messages": [{"role": "user", "content": prompt}]}

            # Stream updates from the data analysis graph
            with st.spinner("Processing..."):
                try:
                    # Stream updates using the centralized session_config
                    for update in graph.stream(
                        input_message,
                        config=session_config,
                        stream_mode="updates",
                    ):
                        # Update received: update
                        process_update(update) # Process each update chunk
                except NameError:
                    st.error("Error: The analysis graph instance ('graph') is not defined.")
                    # Attempted to use 'graph.stream' but 'graph' is not defined.
                except Exception as e:
                    st.error(f"Error during graph execution: {e}")
                    # Error in graph stream


# --- Literature Search Interface Function ---
def show_literature_interface(container=st):
    """Displays the chat interface for literature search."""
    with container:
        st.subheader("Literature Search 📚")

        # Optional: Display study context
        # st.caption(f"Context: {st.session_state.study_info.get('objective', 'N/A')}")

        chat_container_literature = st.container(height=650) # Container with fixed height
        with chat_container_literature:
            # Display initial message if history is empty
            if not st.session_state.literature_messages:
                 st.info("Use the chat below to search for scientific literature.")

            # Display literature chat messages
            for message in st.session_state.literature_messages:
                role = message.get("role", "assistant")
                with st.chat_message(role):
                    # Handle messages containing article cards
                    if message.get("articles"):
                         st.write(message.get("content", "")) # Display text part first
                         for article in message["articles"]:
                             # Display each article in a bordered container
                             with st.container(border=True):
                                 # Basic article info
                                 st.markdown(f"**{article.get('title', 'N/A')}**")
                                 st.caption(f"{article.get('authors', 'N/A')} - {article.get('journal', 'N/A')} ({article.get('year', 'N/A')})")

                                 # Link button if URL exists
                                 article_link = article.get('link')
                                 if article_link:
                                     st.link_button("Go to Article", article_link, use_container_width=True)

                                 # Expander for the abstract
                                 with st.expander("View Abstract"):
                                     st.write(article.get('abstract', 'No abstract available.'))
                    else:
                        # Display regular text messages
                        st.write(message.get("content", "Empty message"))

        # --- Literature Search Chat Input ---
        literature_prompt = st.chat_input("Search literature...", key="chat_input_literature")
        if literature_prompt:
            # Add user message to literature history
            st.session_state.literature_messages.append({"role": "user", "content": literature_prompt})

            # --- Call Literature Search Backend ---
            with st.spinner("Searching literature..."):
                try:
                    # Call the PubMed search function
                    articles = search_pmc_articles(literature_prompt)
                    # Found articles count for query: 'literature_prompt'

                    # Format the response message
                    if articles:
                        response_content = f"Found {len(articles)} articles related to '{literature_prompt}':"
                    else:
                        response_content = f"No articles found matching '{literature_prompt}'."

                    # Add assistant response (with articles) to literature history
                    st.session_state.literature_messages.append({
                        "role": "assistant",
                        "content": response_content,
                        "articles": articles # Attach the list of found articles
                    })
                except Exception as e:
                    # Error during literature search
                    st.error(f"An error occurred during the literature search: {e}")
                    # Add error message to chat
                    st.session_state.literature_messages.append({
                        "role": "assistant",
                        "content": f"Sorry, I encountered an error while searching for articles related to '{literature_prompt}'. Please try again later."
                    })
            # --- End Backend Call ---

            st.rerun() # Rerun to display user message and search results/error


# --- Sidebar ---
with st.sidebar:
    st.header("BioLit Analysis") # App name

    # Button to start a new study
    if st.button("➕ New Study", key="new_study_sidebar_btn", use_container_width=True):
        reset_for_new_study() # Reset session state
        st.rerun()

    st.markdown("---")
    st.subheader("My Studies")

    # Display study history from session state
    if not st.session_state.study_history:
        st.info("No studies found in history.")
    else:
        # Display studies newest first
        for study in reversed(st.session_state.study_history):
            study_date_str = "N/A"
            if study.get("created_at"):
                 try:
                     # Parse ISO date string and format it
                     study_date = datetime.fromisoformat(study["created_at"].replace("Z", "+00:00"))
                     study_date_str = study_date.strftime("%Y-%m-%d %H:%M")
                 except ValueError:
                     # Could not parse date string
                     study_date_str = study.get("created_at") # Fallback to original string

            # Display study item using custom CSS class
            st.markdown(f"""
            <div class="study-item">
                <div class="study-item-title">{study.get('title', 'Untitled Study')}</div>
                <div class="study-item-details">Created: {study_date_str}</div>
                <div class="study-item-details">Dataset: {study.get('dataset_name', 'N/A')}</div>
            </div>
            """, unsafe_allow_html=True)
            # Optional: Add button to load/switch study
            # if st.button(f"Load {study.get('title', 'Study')}", key=f"load_{study.get('id')}"):
            #    load_study(study.get('id')) # Requires load_study implementation
            #    st.rerun()


# --- Main Application Logic ---
if st.session_state.get("show_chat", False):
    # If chat should be shown, display side-by-side interfaces
    col1, col2 = st.columns(2)
    show_chat_interface(col1) # Data analysis chat in left column
    show_literature_interface(col2) # Literature search in right column
else:
    # Otherwise, show the setup interface
    show_setup_interface()
