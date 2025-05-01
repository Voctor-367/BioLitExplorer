from langchain_core.prompts import ChatPromptTemplate


# 1. Define the prompt template for query enrichment
query_enrich_template = ChatPromptTemplate.from_template(
    """You are an expert in search strategies for biomedical literature. Your task is to receive a question or topic from a user in natural language and convert it into an optimized and enriched search string for PubMed, using Chain-of-Thought reasoning.

    --- Current question/topic submitted by user: ---

    **User Query:** {user_query}

    Follow EXACTLY these steps in your reasoning:

    1.  **Analyze the user query and list the main biomedical concepts or entities (e.g. diseases, drugs, interventions, populations, outcomes). Ignore common linking words.
    2.  **Brainstorm Related Terms/Synonyms:** For each key concept identified, list common synonyms, spelling/morphological variations (e.g. plurals, wildcard radicals `*`) and related terms that could be used in scientific literature.
    3.  **Suggest MeSH (Best Effort) Terms:** Based on your general knowledge, suggest possible MeSH (Medical Subject Headings) terms that would correspond to the key concepts. **Important: Make it clear that these are suggestions. Use the format `Concept[MeSH Terms]`. Also consider relevant MeSH Subheadings (e.g. `Therapy`, `Prevention & Control`).
    4.  **PubMed Query Construction:** Combine the identified and suggested terms using PubMed's Boolean syntax (`AND`, `OR`, `NOT`) and field specifiers (`[Title/Abstract]`, `[MeSH Terms]`, `[Subheading]`).
        * Use `OR` to group synonyms, related terms and the suggested MeSH term for the *same* concept. Include the original term and variations in the `[Title/Abstract]` as fallback.
        * Use `AND` to connect the *different* key concepts.
        * Use brackets `()` to correctly group `OR` clauses.
        * Use the `*` wildcard to capture variations. Use quotation marks `“”` for exact phrases (e.g. “type 2 diabetes”).
    5.  **Review and Refinement:** Review the constructed query. Does it capture the original intent? Add common filters if appropriate (e.g. `English[Language]`, date limits for “new” treatments).

    **Output Format:** {desired_format}. **IMPORTANT: The final string of the PubMed query must NOT contain ANY external formatting characters, such as backticks or quotation marks surrounding the entire query. Just the raw query.

    --- Example 1 ---

    **User Query:** effect of aspirin on heart attack prevention

    **Chain of Thought:**
    1.  **Identify Key Concepts:** Aspirin (Drug), Prevention (Intervention/Outcome), Heart Attack (Disease/Condition).
    2.  **Brainstorm Related Terms/Synonyms:** Aspirin: aspirin, acetylsalicylic acid. Prevention: prevent\*, prevention, prophylaxis. Heart Attack: heart attack, myocardial infarction, MI.
    3.  **Suggested MeSH Terms:** Aspirin: `Aspirin[MeSH Terms]`. Prevention: `Prevention & Control[Subheading]`. Heart Attack: `Myocardial Infarction[MeSH Terms]`.
    4.  **Construction of the PubMed Query:**
        * Aspirin: `(“Aspirin”[MeSH Terms] OR Aspirin[Title/Abstract] OR “acetylsalicylic acid”[Title/Abstract])`
        * Prevention: `(“Prevention & Control”[Subheading] OR prevent*[Title/Abstract] OR prophylaxis[Title/Abstract])`
        * Heart Attack: `("Myocardial Infarction"[MeSH Terms] OR "heart attack"[Title/Abstract] OR MI[Title/Abstract])`
        * Combine: `(...) AND (...) AND (...)`
    5.  **Revision and Refinement:** The structure is good, it combines MeSH and free terms, it uses operators correctly. No obvious additional filters needed.

    **Final PubMed Query:**
    ("Aspirin"[MeSH Terms] OR Aspirin[Title/Abstract] OR "acetylsalicylic acid"[Title/Abstract]) AND ("Prevention & Control"[Subheading] OR prevent*[Title/Abstract] OR prophylaxis[Title/Abstract]) AND ("Myocardial Infarction"[MeSH Terms] OR "heart attack"[Title/Abstract] OR MI[Title/Abstract])

    --- Example 2 ---

    **User Query:** new treatments for type 2 diabetes in children

    **Chain of Thought:**
    1.  **Identify Key Concepts:** New Treatments (Intervention), Type 2 Diabetes (Disease), Children (Population).
    2.  **Brainstorm Related Terms/Synonyms:** New Treatments: new, novel, recent, latest + treatment, therapy, management. Type 2 diabetes: type 2 diabetes, T2DM, type II diabetes. Children: child\*, pediatric, paediatric, adolescent.
    3.  **Suggested MeSH Terms (Best Effort):** New Treatments: `Therapeutics[MeSH Terms]` or `Therapy[Subheading]`. Type 2 Diabetes: `"Diabetes Mellitus, Type 2"[MeSH Terms]`. Children: `Child[MeSH Terms]`, `Adolescent[MeSH Terms]`.


    4.  **Construction of the PubMed Query:**
        * Treatment: `(Therapeutics[MeSH Terms] OR Therapy[Subheading] OR treatment[Title/Abstract] OR therapy[Title/Abstract] OR management[Title/Abstract])`
        * Diabetes T2: `("Diabetes Mellitus, Type 2"[MeSH Terms] OR "type 2 diabetes"[Title/Abstract] OR T2DM[Title/Abstract])`
        * Children: `(Child[MeSH Terms] OR Adolescent[MeSH Terms] OR child*[Title/Abstract] OR pediatric[Title/Abstract] OR paediatric[Title/Abstract])`
        * Combine: `(...) AND (...) AND (...)`
    5.  **Review and Refinement:** The query covers the concepts well. The word "new" suggests a data filter. Adding `English[Language]` is good practice. Let's add a filter for the last 5 years.

        **PubMed Final query:**
    ((Therapeutics[MeSH Terms] OR Therapy[Subheading] OR treatment[Title/Abstract] OR therapy[Title/Abstract] OR management[Title/Abstract]) AND ("Diabetes Mellitus, Type 2"[MeSH Terms] OR "type 2 diabetes"[Title/Abstract] OR T2DM[Title/Abstract]) AND (Child[MeSH Terms] OR Adolescent[MeSH Terms] OR child*[Title/Abstract] OR pediatric[Title/Abstract] OR pediatric[Title/Abstract])) AND English[Language] AND (“last 5 years”[Date - Publication])

        Warning: Follow the output format: {desired_format}. **Remember: The final string of the query must NOT have ANY external formatting such as quotes.**
    """
)




