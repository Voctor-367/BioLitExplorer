import streamlit as st  
import time
from Bio import Entrez
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional


# --- Import Enrichment Functions ---
try:
    from src.app.graphs.query_enricher import get_query_enrichment_chain, enrich_query
    ENRICHMENT_ENABLED = True
except ImportError:
    try:
        from src.app.graps.query_enricher import get_query_enrichment_chain, enrich_query
        ENRICHMENT_ENABLED = True
    except ImportError:
         ENRICHMENT_ENABLED = False
         def get_query_enrichment_chain(): return None
         def enrich_query(q, c): return q

# --- Entrez configuration ---
# (Como antes)
NCBI_EMAIL=st.secrets["NCBI_EMAIL"]
NCBI_API_KEY=st.secrets["NCBI_API_KEY"]

if not NCBI_EMAIL or NCBI_EMAIL == "seu_email_dedicado@exemplo.com":
   raise ValueError("CRITICAL ERROR: Entrez email (NCBI_EMAIL) not configured")
Entrez.email = NCBI_EMAIL
if NCBI_API_KEY: Entrez.api_key = NCBI_API_KEY
else: print("[WARNING] NCBI API Key not configured. Using lower rate limits.")

# Initialize enrichment chain globally (if enabled)
if ENRICHMENT_ENABLED:
    print("[INFO] Initializing enrichment chain (may take a while)...")
    try: enrichment_chain_global = get_query_enrichment_chain(); print("[INFO] Cadeia de enriquecimento pronta.")
    except Exception as e: print(f"[ERRO] Falha ao inicializar cadeia: {e}"); ENRICHMENT_ENABLED = False; enrichment_chain_global = None
else: enrichment_chain_global = None

# --- Constants ---
TARGET_COMPLETE_COUNT_DEFAULT = 4 # O número desejado de artigos completos no final
FETCH_MULTIPLIER = 2.0            # Fator pelo qual multiplicar o alvo para busca inicial (ex: 4 * 2 = 8)

# --- Internal entrez functions ---
# (_search_pmc_ids, _fetch_pmc_xml, _parse_single_article_xml, _parse_pmc_xml_results)
def _parse_single_article_xml(article_elem: ET.Element) -> Optional[Dict[str, str]]:
    """
    Parses a single <article> element from the PMC XML.
    Returns a dictionary with the MANDATORY fields (including year) or None if key fields are missing.
    """
    
    article_data = {}
    extracted_authors = []

    pmc_id_elem = article_elem.find('.//article-id[@pub-id-type="pmc"]')
    if pmc_id_elem is not None and pmc_id_elem.text: article_data['pmc_id'] = pmc_id_elem.text.strip()
    else: return None

    title_elem = article_elem.find('.//article-title')
    if title_elem is not None: article_data['title'] = "".join(title_elem.itertext()).strip()
    else: article_data['title'] = "N/A"

    abstract_text = ""
    abstract_elem = article_elem.find('.//abstract')
    if abstract_elem is not None:
         for element in abstract_elem.findall('.//*'):
             element_text = " ".join("".join(element.itertext()).split())
             if element_text: abstract_text += element_text + " "
         if not abstract_text: abstract_text = " ".join("".join(abstract_elem.itertext()).split())
    article_data['abstract'] = abstract_text.strip() if abstract_text else "N/A"

    for contrib_group in article_elem.findall('.//contrib-group'):
        for contrib in contrib_group.findall('.//contrib[@contrib-type="author"]'):
            surname_elem = contrib.find('.//name/surname')
            given_names_elem = contrib.find('.//name/given-names')
            author_name = ""
            if given_names_elem is not None and given_names_elem.text: author_name += given_names_elem.text.strip()
            if surname_elem is not None and surname_elem.text:
                if author_name: author_name += " "; author_name += surname_elem.text.strip()
            if author_name: extracted_authors.append(author_name.strip())
    article_data['authors'] = ", ".join(extracted_authors[:4]) if extracted_authors else "N/A"

    year_str = "N/A"
    pub_date_elem = article_elem.find('.//pub-date[@pub-type="epub"]')
    if pub_date_elem is None: pub_date_elem = article_elem.find('.//pub-date[@pub-type="ppub"]')
    if pub_date_elem is None: pub_date_elem = article_elem.find('.//pub-date')
    if pub_date_elem is not None:
        year_elem = pub_date_elem.find('./year')
        if year_elem is not None and year_elem.text and year_elem.text.strip().isdigit(): year_str = year_elem.text.strip()
        else:
            medline_date_elem = pub_date_elem.find('./medline-date')
            if medline_date_elem is not None and medline_date_elem.text:
                 date_str = medline_date_elem.text.strip();
                 if len(date_str) >= 4 and date_str[:4].isdigit(): year_str = date_str[:4]
    article_data['year'] = year_str

    article_data['link'] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{article_data['pmc_id']}/"
    return article_data

# Funções _search_pmc_ids, _fetch_pmc_xml, _parse_pmc_xml_results também permanecem como antes

def _search_pmc_ids(query: str, max_results: int) -> list:
    """Searches for IDs in the PMC (internal function)."""
    if not query: return []
    print(f"[INFO] Buscando até {max_results} IDs no PMC para: '{query[:50]}...'")
    try:
        handle = Entrez.esearch(db="pmc", term=query, retmax=str(max_results), sort="relevance")
        record = Entrez.read(handle)
        handle.close()
        pmc_ids = record.get("IdList", [])
        print(f"[INFO] Found {len(pmc_ids)} IDs in PMC.")
        return pmc_ids
    except Exception as e:
        print(f"[ERROR] Error during Entrez.esearch: {e}")
        return []
    finally:
        delay = 0.11 if NCBI_API_KEY else 0.34
        time.sleep(delay)

def _fetch_pmc_xml(pmc_ids: list) -> str:
    """Searches the details (XML) for PMC IDs (Internal function)."""
    if not pmc_ids: return ""
    print(f"[INFO] Searching for XML details for {len(pmc_ids)} IDs in PMC...")
    ids_string = ",".join(pmc_ids)
    xml_string_decoded = ""
    try:
        handle = Entrez.efetch(db="pmc", id=ids_string, rettype="xml", retmode="xml")
        xml_data_bytes = handle.read()
        handle.close()
        print(f"[INFO] XML data received (Size: {len(xml_data_bytes)} bytes).")
        try:
            xml_string_decoded = xml_data_bytes.decode('utf-8')
        except UnicodeDecodeError:
            print("[AVISO] Failed to decode XML as UTF-8, trying to latin-1.")
            try: xml_string_decoded = xml_data_bytes.decode('latin-1')
            except UnicodeDecodeError: print("[ERRO] It was not possible to decode the XML.")
    except Exception as e:
        print(f"[ERRO] Erro during Entrez.efetch: {e}")
    finally:
        delay = 0.11 if NCBI_API_KEY else 0.34
        time.sleep(delay)
    return xml_string_decoded

def _parse_pmc_xml_results(xml_string: str) -> List[Dict[str, str]]:
    """
    Parses the complete XML string containing multiple articles.
    Use _parse_single_article_xml for each one.
    Returns a list of dictionaries, each representing a successfully parsed article.
    """
    parsed_articles_list = []
    if not xml_string: return parsed_articles_list
    try:
        root = ET.fromstring(xml_string)
        processed_pmc_ids = set()
        for article_elem in root.findall('.//article'):
            parsed_data = _parse_single_article_xml(article_elem)
            if parsed_data and parsed_data['pmc_id'] not in processed_pmc_ids:
                parsed_articles_list.append(parsed_data)
                processed_pmc_ids.add(parsed_data['pmc_id'])
    except ET.ParseError as e: print(f"[ERRO PARSER] Error when parsing XML: {e}")
    except Exception as e: print(f"[ERRO PARSER] Unexpected error during parsing: {e}")
    print(f"[INFO] Parsing completed. Extracted {len(parsed_articles_list)} single articles.")
    return parsed_articles_list


# --- Main Exportable Function  ---

def search_pmc_articles(
    query: str,
    target_count: int = TARGET_COMPLETE_COUNT_DEFAULT, # Desired number of FULL articles
    fetch_multiplier: float = FETCH_MULTIPLIER       # Factor for initial search
) -> List[Dict[str, str]]:
    """
    Searches for articles in PMC, filters by completeness and returns a target number of results.

    Args:
         query (str): The user's search question or topic.
         target_count (int): The desired number of complete articles in the final result.
         fetch_multiplier (float): Factor by which to multiply target_count to
         determine how many articles to initially fetch.

    Returns:
         List[Dict[str, str]]: A list of dictionaries, containing up to `target_count`
         full articles ('pmc_id', 'link', 'authors', 'title',
         'abstract', 'year'). Returns empty list in case of error
         or if no complete article is found.
    """
    print(f"\n--- Starting to search for articles to query: '{query[:60]}...' ---")
    print(f"[INFO] Final objective: {target_count} full articles.")
    search_query = query

    # 1. Enrich Query (if enabled)
    if ENRICHMENT_ENABLED and enrichment_chain_global:
        try:
            print("[INFO] Trying to enrich the query...")
            enriched = enrich_query(query, enrichment_chain_global)
            if enriched and enriched != query:
                search_query = enriched
                print(f"[INFO] Enriched query used: '{search_query[:60]}...'")
            else:
                 print("[INFO] Enrichment did not change the query or failed, using original.")
        except Exception as enrich_e:
            print(f"[ERRO] Error during query enrichment: {enrich_e}")
            print("[INFO] Using original query.")
            search_query = query
    if not search_query:
        print("[ERRO] Final query for search is empty. Aborting.")
        return []

    # 2. Calculate how many IDs to look for initially
    # Ensures that we look for at least the target number, and applies the multiplier
    initial_max_results = max(target_count, int(target_count * fetch_multiplier))
    print(f"[INFO] Initially searching up to {initial_max_results} IDs to guarantee the goal.")

    # 3. Search for IDs in the PMC
    pmc_results_ids = _search_pmc_ids(search_query, initial_max_results)

    # 4. If found IDs, search and parse the XML details
    all_parsed_articles: List[Dict[str, str]] = []
    if pmc_results_ids:
        articles_xml = _fetch_pmc_xml(pmc_results_ids)
        if articles_xml:
            all_parsed_articles = _parse_pmc_xml_results(articles_xml)
        else:
             print("[WARNIG] It was not possible to obtain or decode the XML data of the articles.")
    else:
        print("[INFO] No article ID found in PMC for this query.")

    # 5. Filter by Completeness and Limit to Target Number
    complete_articles: List[Dict[str, str]] = []
    if all_parsed_articles:
        print(f"[INFO] Filtering {len(all_parsed_articles)} articles parsed for completeness...")
        articles_checked = 0
        for article in all_parsed_articles:
            articles_checked += 1
            # Checks that all MANDATORY fields have valid values (not None, not “N/A”, not "")
            pmc_id = article.get("pmc_id")
            title = article.get("title")
            authors = article.get("authors")
            abstract = article.get("abstract")
            year = article.get("year")
            link = article.get("link") # Link is derived, it will always exist if pmc_id exists

            is_complete = (
                pmc_id and  # Ensures that the ID exists
                title not in [None, "N/A", ""] and
                authors not in [None, "N/A", ""] and
                abstract not in [None, "N/A", ""] and
                year not in [None, "N/A", ""]
                # Don't need to check ‘link’ because it depends on the pmc_id
            )

            if is_complete:
                complete_articles.append(article)
                # Verifica se já atingimos a meta
                if len(complete_articles) >= target_count:
                    print(f"[INFO] Target of {target_count} complete articles achieved after checking {articles_checked} articles.")
                    break # Stop adding as soon as the target is met
            # else:
                # print(f"[DEBUG] Article {pmc_id or 'sem ID'} discarded due to incomplete data.")

        print(f"[INFO] Filtering completed. Found {len(complete_articles)} complete articles.")
        if len(complete_articles) < target_count:
            print(f"[WARNING] It was not possible to find {target_count} complete articles. Returning {len(complete_articles)}.")

    else:
        print("[INFO] No articles parsed to filter.")

    # 6. Return the list of complete articles (limited to target_count)
    print(f"--- Search completed. Returning {len(complete_articles)} full articles processed. ---")
    print(f"\n\n[INFO] Full articles returned: {complete_articles[:3]}...") # Displays the first 3 for debugging
    return complete_articles # The list will already be limited by the break in the loop


# --- Test Block (Only executed when running the script directly) ---
if __name__ == "__main__":
    print("\n" + "="*30 + " STARTING MODULE TEST " + "="*30)

    test_query = input("Enter a test query (ex: 'artificial intelligence medicine'): ")
    target_num_str = input(f"How many COMPLETE articles do you want at the end? (Default: {TARGET_COMPLETE_COUNT_DEFAULT}): ")
    fetch_mult_str = input(f"Which multiplier to use for initial search? (Default: {FETCH_MULTIPLIER}): ")

    try:
        target_num = int(target_num_str) if target_num_str else TARGET_COMPLETE_COUNT_DEFAULT
    except ValueError:
        print(f"Invalid entry for target number, using pattern {TARGET_COMPLETE_COUNT_DEFAULT}.")
        target_num = TARGET_COMPLETE_COUNT_DEFAULT

    try:
        fetch_mult = float(fetch_mult_str) if fetch_mult_str else FETCH_MULTIPLIER
    except ValueError:
         print(f"Invalid entry for multiplier, using pattern {FETCH_MULTIPLIER}.")
         fetch_mult = FETCH_MULTIPLIER

    if test_query:
        # Call the main exportable function with the test parameters
        results = search_pmc_articles(
            test_query,
            target_count=target_num,
            fetch_multiplier=fetch_mult
        )

        print("\n" + "*"*30 + " RESULTS RETURNED BY FUNCTION  " + "*"*30)
        if results:
            import json
            print(f"The function returned {len(results)} complete articles:")
            print(json.dumps(results, indent=2))
        else:
            print("The function returned an empty list.")
        print("*"*30 + " END OF RESULTS  " + "*"*30)
    else:
        print("No test query provided.")

    print("\n" + "="*30 + " END OF MODULE TEST " + "="*30)
