from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings


# Verify if the API key was loaded (optional, for debugging)
# if not os.getenv("GOOGLE_API_KEY"):
#      # Error: GOOGLE_API_KEY environment variable not found.
# else:
#     # GOOGLE_API_KEY found.

try:
    # Initialize the Google Generative AI chat model
    # Credentials are automatically handled if GOOGLE_API_KEY env var is set
    model = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-04-17", temperature=0.5) # Specify desired model and temperature
    # Gemini model in use: model.model

    # Initialize the Google Generative AI embeddings model
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001") # Specify desired embedding model
    # Google Gemini model initialized successfully.

except Exception as e:
    # Error initializing Google Gemini model
    # Could be due to invalid key, quota exceeded, etc.
    raise e # Re-raise the exception after logging (or handling)

