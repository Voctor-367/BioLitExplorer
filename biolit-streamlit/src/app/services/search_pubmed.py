import streamlit as st  
import time
from Bio import Entrez
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional


# --- Importar Funções de Enriquecimento ---
# (Mantendo sua lógica de importação com fallback)
try:
    from src.app.graphs.query_enricher import get_query_enrichment_chain, enrich_query
    ENRICHMENT_ENABLED = True
except ImportError:
    try:
        from src.app.graps.query_enricher import get_query_enrichment_chain, enrich_query
        ENRICHMENT_ENABLED = True
    except ImportError:
         print("[AVISO] Falha ao importar query_enricher. O enriquecimento será desabilitado.")
         ENRICHMENT_ENABLED = False
         def get_query_enrichment_chain(): return None
         def enrich_query(q, c): return q

# --- Configuração Entrez ---
# (Como antes)
NCBI_EMAIL=st.secrets["NCBI_EMAIL"]
NCBI_API_KEY=st.secrets["NCBI_API_KEY"]

if not NCBI_EMAIL or NCBI_EMAIL == "seu_email_dedicado@exemplo.com":
   raise ValueError("ERRO CRÍTICO: Email do Entrez (NCBI_EMAIL) não configurado!")
Entrez.email = NCBI_EMAIL
if NCBI_API_KEY: Entrez.api_key = NCBI_API_KEY
else: print("[AVISO] API Key do NCBI não configurada. Usando limites de taxa menores.")

# Inicializar cadeia de enriquecimento globalmente (se habilitada)
# (Como antes)
if ENRICHMENT_ENABLED:
    print("[INFO] Inicializando cadeia de enriquecimento (pode levar um tempo)...")
    try: enrichment_chain_global = get_query_enrichment_chain(); print("[INFO] Cadeia de enriquecimento pronta.")
    except Exception as e: print(f"[ERRO] Falha ao inicializar cadeia: {e}"); ENRICHMENT_ENABLED = False; enrichment_chain_global = None
else: enrichment_chain_global = None

# --- Constantes ---
TARGET_COMPLETE_COUNT_DEFAULT = 4 # O número desejado de artigos completos no final
FETCH_MULTIPLIER = 2.0            # Fator pelo qual multiplicar o alvo para busca inicial (ex: 4 * 2 = 8)

# --- Funções Entrez Internas ---
# (_search_pmc_ids, _fetch_pmc_xml, _parse_single_article_xml, _parse_pmc_xml_results)
# Mantêm-se exatamente como na versão anterior (com a extração do ano incluída)
# Apenas como referência, a assinatura e docstring de _parse_single_article_xml:
def _parse_single_article_xml(article_elem: ET.Element) -> Optional[Dict[str, str]]:
    """
    Parseia um único elemento <article> do XML do PMC.
    Retorna um dicionário com os campos OBRIGATÓRIOS (incluindo ano) ou None se campos chave faltarem.
    """
    # ... (lógica interna da função permanece a mesma, incluindo a extração do ano) ...
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
    """Busca IDs no PMC (Função interna)."""
    if not query: return []
    print(f"[INFO] Buscando até {max_results} IDs no PMC para: '{query[:50]}...'")
    try:
        handle = Entrez.esearch(db="pmc", term=query, retmax=str(max_results), sort="relevance")
        record = Entrez.read(handle)
        handle.close()
        pmc_ids = record.get("IdList", [])
        print(f"[INFO] Encontrados {len(pmc_ids)} IDs no PMC.")
        return pmc_ids
    except Exception as e:
        print(f"[ERRO] Erro durante Entrez.esearch: {e}")
        return []
    finally:
        delay = 0.11 if NCBI_API_KEY else 0.34
        time.sleep(delay)

def _fetch_pmc_xml(pmc_ids: list) -> str:
    """Busca os detalhes (XML) para IDs do PMC (Função interna)."""
    if not pmc_ids: return ""
    print(f"[INFO] Buscando detalhes XML para {len(pmc_ids)} IDs do PMC...")
    ids_string = ",".join(pmc_ids)
    xml_string_decoded = ""
    try:
        handle = Entrez.efetch(db="pmc", id=ids_string, rettype="xml", retmode="xml")
        xml_data_bytes = handle.read()
        handle.close()
        print(f"[INFO] Dados XML recebidos (Tamanho: {len(xml_data_bytes)} bytes).")
        try:
            xml_string_decoded = xml_data_bytes.decode('utf-8')
        except UnicodeDecodeError:
            print("[AVISO] Falha ao decodificar XML como UTF-8, tentando latin-1.")
            try: xml_string_decoded = xml_data_bytes.decode('latin-1')
            except UnicodeDecodeError: print("[ERRO] Não foi possível decodificar o XML.")
    except Exception as e:
        print(f"[ERRO] Erro durante Entrez.efetch: {e}")
    finally:
        delay = 0.11 if NCBI_API_KEY else 0.34
        time.sleep(delay)
    return xml_string_decoded

def _parse_pmc_xml_results(xml_string: str) -> List[Dict[str, str]]:
    """
    Parseia a string XML completa contendo múltiplos artigos.
    Usa _parse_single_article_xml para cada um.
    Retorna uma lista de dicionários, cada um representando um artigo parseado com sucesso.
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
    except ET.ParseError as e: print(f"[ERRO PARSER] Erro ao parsear o XML: {e}")
    except Exception as e: print(f"[ERRO PARSER] Erro inesperado durante parsing: {e}")
    print(f"[INFO] Parsing concluído. Extraídos {len(parsed_articles_list)} artigos únicos.")
    return parsed_articles_list


# --- Função Principal Exportável (MODIFICADA) ---

def search_pmc_articles(
    query: str,
    target_count: int = TARGET_COMPLETE_COUNT_DEFAULT, # Número desejado de artigos COMPLETOS
    fetch_multiplier: float = FETCH_MULTIPLIER       # Fator para busca inicial
) -> List[Dict[str, str]]:
    """
    Busca artigos no PMC, filtra por completude e retorna um número alvo de resultados.

    Args:
        query (str): A pergunta ou tópico de busca do usuário.
        target_count (int): O número desejado de artigos completos no resultado final.
        fetch_multiplier (float): Fator pelo qual multiplicar target_count para
                                  determinar quantos artigos buscar inicialmente.

    Returns:
        List[Dict[str, str]]: Uma lista de dicionários, contendo até `target_count`
                               artigos completos ('pmc_id', 'link', 'authors', 'title',
                               'abstract', 'year'). Retorna lista vazia em caso de erro
                               ou se nenhum artigo completo for encontrado.
    """
    print(f"\n--- Iniciando busca de artigos para query: '{query[:60]}...' ---")
    print(f"[INFO] Objetivo final: {target_count} artigos completos.")
    search_query = query

    # 1. Enriquecer a Query (se habilitado)
    # (Lógica de enriquecimento como antes)
    if ENRICHMENT_ENABLED and enrichment_chain_global:
        try:
            print("[INFO] Tentando enriquecer a query...")
            enriched = enrich_query(query, enrichment_chain_global)
            if enriched and enriched != query:
                search_query = enriched
                print(f"[INFO] Query enriquecida utilizada: '{search_query[:60]}...'")
            else:
                 print("[INFO] Enriquecimento não alterou a query ou falhou, usando original.")
        except Exception as enrich_e:
            print(f"[ERRO] Erro durante o enriquecimento da query: {enrich_e}")
            print("[INFO] Usando query original.")
            search_query = query
    if not search_query:
        print("[ERRO] Query final para busca está vazia. Abortando.")
        return []

    # 2. Calcular quantos IDs buscar inicialmente
    # Garante que buscamos pelo menos o número alvo, e aplica o multiplicador
    initial_max_results = max(target_count, int(target_count * fetch_multiplier))
    print(f"[INFO] Buscando inicialmente até {initial_max_results} IDs para garantir a meta.")

    # 3. Realizar a Busca de IDs no PMC
    pmc_results_ids = _search_pmc_ids(search_query, initial_max_results)

    # 4. Se encontrou IDs, buscar e parsear os detalhes XML
    all_parsed_articles: List[Dict[str, str]] = []
    if pmc_results_ids:
        articles_xml = _fetch_pmc_xml(pmc_results_ids)
        if articles_xml:
            all_parsed_articles = _parse_pmc_xml_results(articles_xml)
        else:
             print("[AVISO] Não foi possível obter ou decodificar os dados XML dos artigos.")
    else:
        print("[INFO] Nenhum ID de artigo encontrado no PMC para esta query.")

    # 5. Filtrar por Completude e Limitar ao Número Alvo
    complete_articles: List[Dict[str, str]] = []
    if all_parsed_articles:
        print(f"[INFO] Filtrando {len(all_parsed_articles)} artigos parseados para completude...")
        articles_checked = 0
        for article in all_parsed_articles:
            articles_checked += 1
            # Verifica se todos os campos OBRIGATÓRIOS têm valores válidos (não None, não "N/A", não "")
            pmc_id = article.get("pmc_id")
            title = article.get("title")
            authors = article.get("authors")
            abstract = article.get("abstract")
            year = article.get("year")
            link = article.get("link") # Link é derivado, sempre existirá se pmc_id existir

            is_complete = (
                pmc_id and  # Garante que o ID existe
                title not in [None, "N/A", ""] and
                authors not in [None, "N/A", ""] and
                abstract not in [None, "N/A", ""] and
                year not in [None, "N/A", ""]
                # Não precisa checar 'link' pois depende do pmc_id
            )

            if is_complete:
                complete_articles.append(article)
                # Verifica se já atingimos a meta
                if len(complete_articles) >= target_count:
                    print(f"[INFO] Meta de {target_count} artigos completos atingida após verificar {articles_checked} artigos.")
                    break # Para de adicionar assim que a meta for cumprida
            # else:
                # print(f"[DEBUG] Artigo {pmc_id or 'sem ID'} descartado por dados incompletos.")

        print(f"[INFO] Filtragem concluída. Encontrados {len(complete_articles)} artigos completos.")
        if len(complete_articles) < target_count:
            print(f"[AVISO] Não foi possível encontrar {target_count} artigos completos. Retornando {len(complete_articles)}.")

    else:
        print("[INFO] Nenhum artigo parseado para filtrar.")

    # 6. Retornar a lista de artigos completos (limitada a target_count)
    print(f"--- Busca concluída. Retornando {len(complete_articles)} artigos completos processados. ---")
    print(f"\n\n[INFO] Artigos completos retornados: {complete_articles[:3]}...") # Exibe os 3 primeiros para depuração
    return complete_articles # A lista já estará limitada pelo break no loop


# --- Bloco de Teste (Executado apenas ao rodar o script diretamente) ---
if __name__ == "__main__":
    print("\n" + "="*30 + " INICIANDO TESTE DO MÓDULO " + "="*30)

    test_query = input("Digite uma query de teste (ex: 'artificial intelligence medicine'): ")
    target_num_str = input(f"Quantos artigos COMPLETOS você deseja no final? (Padrão: {TARGET_COMPLETE_COUNT_DEFAULT}): ")
    fetch_mult_str = input(f"Qual multiplicador usar para busca inicial? (Padrão: {FETCH_MULTIPLIER}): ")

    try:
        target_num = int(target_num_str) if target_num_str else TARGET_COMPLETE_COUNT_DEFAULT
    except ValueError:
        print(f"Entrada inválida para número alvo, usando padrão {TARGET_COMPLETE_COUNT_DEFAULT}.")
        target_num = TARGET_COMPLETE_COUNT_DEFAULT

    try:
        fetch_mult = float(fetch_mult_str) if fetch_mult_str else FETCH_MULTIPLIER
    except ValueError:
         print(f"Entrada inválida para multiplicador, usando padrão {FETCH_MULTIPLIER}.")
         fetch_mult = FETCH_MULTIPLIER

    if test_query:
        # Chamar a função principal exportável com os parâmetros de teste
        results = search_pmc_articles(
            test_query,
            target_count=target_num,
            fetch_multiplier=fetch_mult
        )

        print("\n" + "*"*30 + " RESULTADOS RETORNADOS PELA FUNÇÃO " + "*"*30)
        if results:
            import json
            print(f"A função retornou {len(results)} artigos completos:")
            print(json.dumps(results, indent=2))
        else:
            print("A função retornou uma lista vazia.")
        print("*"*30 + " FIM DOS RESULTADOS " + "*"*30)
    else:
        print("Nenhuma query de teste fornecida.")

    print("\n" + "="*30 + " FIM DO TESTE DO MÓDULO " + "="*30)
