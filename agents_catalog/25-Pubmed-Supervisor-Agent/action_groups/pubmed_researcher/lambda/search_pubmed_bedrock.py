import json
import logging
import httpx
import time
from typing import Dict, Any, List, Optional
from xml.etree import ElementTree as ET

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for searching PubMed articles - Bedrock Agent format.
    
    Args:
        event: Lambda event from Bedrock Agent
        context: Lambda runtime context
        
    Returns:
        dict: Response in Bedrock Agent format
    """
    logger.info(f"Starting search_pubmed Lambda for event: {json.dumps(event)}")

    try:
        # Extract parameters from Bedrock Agent event structure
        action_group = event["actionGroup"]
        api_path = event["apiPath"]
        parameters = event.get("parameters", [])
        http_method = event["httpMethod"]
        
        # Parse parameters from Bedrock Agent format
        query = None
        max_results = 100
        max_records = None
        rerank = "referenced_by"
        
        for param in parameters:
            if param["name"] == "query":
                query = param["value"]
            elif param["name"] == "max_results":
                max_results = int(param["value"]) if param["value"] else 100
            elif param["name"] == "max_records":
                max_records = int(param["value"]) if param["value"] else None
            elif param["name"] == "rerank":
                rerank = param["value"] if param["value"] else "referenced_by"

        # Validate required parameters
        if not query:
            response_body = {"application/json": {"body": "Error: Query parameter is required"}}
            response_code = 400
        else:
            # Perform PubMed search
            try:
                search_results = perform_pubmed_search(query, max_results, max_records, rerank)
                response_body = {"application/json": {"body": search_results}}
                response_code = 200
            except Exception as search_error:
                logger.error(f"Error during PubMed search: {search_error}")
                response_body = {"application/json": {"body": f"Error during PubMed search: {str(search_error)}"}}
                response_code = 500

        # Return response in Bedrock Agent format
        action_response = {
            'actionGroup': action_group,
            'apiPath': api_path,
            'httpMethod': http_method,
            'httpStatusCode': response_code,
            'responseBody': response_body
        }
        
        api_response = {
            'messageVersion': '1.0', 
            'response': action_response
        }
        
        logger.info(f"Returning response: {json.dumps(api_response)}")
        return api_response

    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {e}")
        
        # Error response in Bedrock Agent format
        error_response_body = {"application/json": {"body": f"Unexpected error: {str(e)}"}}
        action_response = {
            'actionGroup': event.get('actionGroup', 'unknown'),
            'apiPath': event.get('apiPath', '/search_pubmed'),
            'httpMethod': event.get('httpMethod', 'POST'),
            'httpStatusCode': 500,
            'responseBody': error_response_body
        }
        
        return {
            'messageVersion': '1.0', 
            'response': action_response
        }


def perform_pubmed_search(query: str, max_results: int = 100, max_records: Optional[int] = None, rerank: str = "referenced_by") -> str:
    """
    Perform PubMed search and return formatted results.
    
    Args:
        query: Search query
        max_results: Maximum number of results to fetch
        max_records: Maximum number of records to return
        rerank: Reranking method
        
    Returns:
        str: Formatted search results
    """
    logger.info(f"Performing PubMed search for query: '{query}'")
    
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    search_url = f"{base_url}/esearch.fcgi"
    fetch_url = f"{base_url}/efetch.fcgi"
    
    # Build search query with commercial use filter
    filtered_query = f"{query} AND \"loattrfree full text\"[sb]"
    
    # Search for article IDs
    search_params = {
        "db": "pubmed",
        "term": filtered_query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }
    
    try:
        search_response = httpx.post(search_url, data=search_params, timeout=30.0)
        search_response.raise_for_status()
        search_data = search_response.json()
    except Exception as e:
        logger.error(f"Error during PubMed search: {e}")
        raise Exception(f"PubMed search failed: {str(e)}")
    
    # Extract PMIDs
    pmids = search_data.get("esearchresult", {}).get("idlist", [])
    if not pmids:
        return f"No articles found for query: '{query}'"
    
    logger.info(f"Found {len(pmids)} articles")
    
    # Limit results if max_records is specified
    if max_records and len(pmids) > max_records:
        pmids = pmids[:max_records]
    
    # Fetch article details
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract"
    }
    
    try:
        fetch_response = httpx.post(fetch_url, data=fetch_params, timeout=60.0)
        fetch_response.raise_for_status()
        articles_xml = fetch_response.text
    except Exception as e:
        logger.error(f"Error fetching article details: {e}")
        raise Exception(f"Failed to fetch article details: {str(e)}")
    
    # Parse XML and extract article information
    try:
        articles = parse_pubmed_xml(articles_xml)
    except Exception as e:
        logger.error(f"Error parsing PubMed XML: {e}")
        raise Exception(f"Failed to parse article data: {str(e)}")
    
    # Calculate citation counts if reranking is enabled
    if rerank == "referenced_by" and len(articles) > 1:
        try:
            articles = calculate_citation_counts(articles)
            articles.sort(key=lambda x: x.get('referenced_by_count', 0), reverse=True)
        except Exception as e:
            logger.warning(f"Citation ranking failed, using original order: {e}")
    
    # Format results
    formatted_results = format_search_results(articles, query)
    return formatted_results


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
                    'referenced_by_count': 0  # Will be updated if citation counting is performed
                }
                
                articles.append(article_data)
                
            except Exception as e:
                logger.warning(f"Error parsing individual article: {e}")
                continue
        
        return articles
        
    except ET.ParseError as e:
        logger.error(f"XML parsing error: {e}")
        raise Exception(f"Invalid XML response from PubMed: {str(e)}")


def calculate_citation_counts(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calculate citation counts for articles within the result set."""
    pmids = [article['pmid'] for article in articles]
    pmid_set = set(pmids)
    
    # Count references between articles in the result set
    for article in articles:
        citation_count = 0
        
        # Simple heuristic: count how many other articles in the set might cite this one
        # This is a simplified approach - in reality, you'd need to fetch reference data
        for other_article in articles:
            if (article['pmid'] != other_article['pmid'] and 
                article['title'].lower() in other_article['abstract'].lower()):
                citation_count += 1
        
        article['referenced_by_count'] = citation_count
    
    return articles


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
        
        citation_info = ""
        if article.get('referenced_by_count', 0) > 0:
            citation_info = f" [Citations in result set: {article['referenced_by_count']}]"
        
        result_lines.extend([
            f"\n{i}. {article['title']}",
            f"   Authors: {authors_str}",
            f"   Journal: {article['journal']} ({article['publication_year']}){citation_info}",
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
