"""
Simplified PubMed Search - No Strands Dependencies

This is a clean, simplified version of the PubMed search functionality
without any Strands framework dependencies.
"""

import httpx
import logging
from typing import Dict, List, Any
from xml.etree.ElementTree import Element
from defusedxml import ElementTree as ET

logger = logging.getLogger(__name__)

def search_pubmed(query: str, max_results: int = 100, max_records: int = None, rerank: str = "referenced_by") -> str:
    """
    Search PubMed for articles matching the query.
    
    Args:
        query: The search query for PubMed
        max_results: Maximum number of results to fetch (default: 100)
        max_records: Maximum number of articles to return (default: None)
        rerank: Reranking method (default: "referenced_by")
    
    Returns:
        str: Formatted search results
    """
    # Parameter validation
    if not query or not isinstance(query, str) or not query.strip():
        raise ValueError("Query parameter is required and must be a non-empty string")
    
    if not isinstance(max_results, int) or max_results < 1 or max_results > 1000:
        max_results = 100
        
    if max_records is not None and (not isinstance(max_records, int) or max_records < 1 or max_records > 100):
        max_records = None
        
    if rerank not in ["referenced_by"]:
        rerank = "referenced_by"

    logger.info(f"Searching PubMed for: {query}")

    try:
        # Build search query with commercial use filter
        filtered_query = f"{query} AND \"loattrfree full text\"[sb]"
        
        # Search for article IDs
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": filtered_query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }
        
        with httpx.Client(timeout=30.0) as client:
            search_response = client.post(search_url, data=search_params)
            search_response.raise_for_status()
            search_data = search_response.json()
        
        # Extract PMIDs
        pmids = search_data.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return f"No articles found for query: '{query}'"
        
        logger.info(f"Found {len(pmids)} articles")
        
        # Limit results if max_records is specified
        if max_records and len(pmids) > max_records:
            pmids = pmids[:max_records]
        
        # Fetch article details
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract"
        }
        
        with httpx.Client(timeout=60.0) as client:
            fetch_response = client.post(fetch_url, data=fetch_params)
            fetch_response.raise_for_status()
            articles_xml = fetch_response.text
        
        # Parse XML and extract article information
        articles = parse_pubmed_xml(articles_xml)
        
        # Format results
        formatted_results = format_search_results(articles, query)
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error in PubMed search: {e}")
        raise Exception(f"PubMed search failed: {str(e)}")


def parse_pubmed_xml(xml_content: str) -> List[Dict[str, Any]]:
    """Parse PubMed XML response and extract article information."""
    try:
        root = ET.fromstring(xml_content)
        articles = []
        
        for article_elem in root.findall(".//PubmedArticle"):
            try:
                pmid_elem = article_elem.find(".//PMID")
                pmid = pmid_elem.text if pmid_elem is not None else "Unknown"
                
                title_elem = article_elem.find(".//ArticleTitle")
                title = title_elem.text if title_elem is not None else "No title available"
                
                abstract_elem = article_elem.find(".//Abstract/AbstractText")
                abstract = abstract_elem.text if abstract_elem is not None else "No abstract available"
                
                # Extract authors
                authors = []
                for author_elem in article_elem.findall(".//Author"):
                    lastname_elem = author_elem.find("LastName")
                    forename_elem = author_elem.find("ForeName")
                    if lastname_elem is not None and forename_elem is not None:
                        authors.append(f"{forename_elem.text} {lastname_elem.text}")
                
                # Extract journal info
                journal_elem = article_elem.find(".//Journal/Title")
                journal = journal_elem.text if journal_elem is not None else "Unknown Journal"
                
                # Extract publication date
                pub_date_elem = article_elem.find(".//PubDate/Year")
                pub_year = pub_date_elem.text if pub_date_elem is not None else "Unknown"
                
                # Extract DOI
                doi_elem = article_elem.find(".//ArticleId[@IdType='doi']")
                doi = doi_elem.text if doi_elem is not None else None
                
                article_data = {
                    'pmid': pmid,
                    'title': title,
                    'abstract': abstract,
                    'authors': authors,
                    'journal': journal,
                    'publication_year': pub_year,
                    'doi': doi,
                    'pubmed_url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                }
                
                articles.append(article_data)
                
            except Exception as e:
                logger.warning(f"Error parsing individual article: {e}")
                continue
        
        return articles
        
    except ET.ParseError as e:
        logger.error(f"XML parsing error: {e}")
        raise Exception(f"Invalid XML response from PubMed: {str(e)}")


def format_search_results(articles: List[Dict[str, Any]], query: str) -> str:
    """Format search results into a readable string."""
    if not articles:
        return f"No articles found for query: '{query}'"
    
    result_lines = [
        f"PubMed Search Results for: '{query}'",
        f"Found {len(articles)} relevant articles:",
        "=" * 50
    ]
    
    for i, article in enumerate(articles, 1):
        authors_str = ", ".join(article['authors'][:3])  # Show first 3 authors
        if len(article['authors']) > 3:
            authors_str += " et al."
        
        result_lines.extend([
            f"\n{i}. {article['title']}",
            f"   Authors: {authors_str}",
            f"   Journal: {article['journal']} ({article['publication_year']})",
            f"   PMID: {article['pmid']}",
            f"   URL: {article['pubmed_url']}",
        ])
        
        if article['doi']:
            result_lines.append(f"   DOI: https://doi.org/{article['doi']}")
        
        # Truncate abstract if too long
        abstract = article['abstract']
        if len(abstract) > 300:
            abstract = abstract[:300] + "..."
        
        result_lines.extend([
            f"   Abstract: {abstract}",
            "-" * 40
        ])
    
    return "\n".join(result_lines)
