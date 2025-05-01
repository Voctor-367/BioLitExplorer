from langchain_core.output_parsers import StrOutputParser
from src.app.prompts.query_enricher_template import query_enrich_template
from src.app.services.azure_open_ai import openai_model # Assuming 'model' is the initialized LLM

def get_query_enrichment_chain():
  """Creates and returns the LCEL chain for query enrichment."""
  # 1. Use the imported template directly
  prompt_template = query_enrich_template

  # 2. Create the LCEL chain: prompt -> LLM -> string output parser
  transformation_chain = prompt_template | openai_model | StrOutputParser()
  return transformation_chain

def enrich_query(user_query: str, chain) -> str:
  """
  Invokes the enrichment chain and returns the enriched query.
  Returns an empty string on error.
  """
  try:
    # Adapt the input dictionary as required by the prompt template
    desired_format = "Unicamente uma string com a query enriquecida para PubMed" # Or get from config
    # Starting enrichment for user_query
    enriched_query_string = chain.invoke({
        "user_query": user_query,
        "desired_format": desired_format
    })
    # Enriched Query result
    # Basic validation: ensure a non-empty string was returned
    if enriched_query_string and isinstance(enriched_query_string, str):
      return enriched_query_string.strip()
      print(f"Enriched  Query: {enriched_query_string}")  
      
    else:
        # Error: Enrichment chain did not return a valid string.
        print(f"Enrichment chain returned an invalid result: {enriched_query_string}")
        
  except Exception as e:
    # Error during query enrichment
    return user_query

# Optional: Block for quick testing of this module
# if __name__ == '__main__':
#     test_query = "vitamin D supplements for osteoporosis in postmenopausal women"
#     enrichment_chain = get_query_enrichment_chain()
#     result = enrich_query(test_query, enrichment_chain)
#     # --- Test of query_enricher Module ---
#     # Original Query: test_query
#     # Enriched Result: result