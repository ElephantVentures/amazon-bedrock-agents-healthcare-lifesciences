"""
Simple Supervisor Agent Handler - No Strands SDK Required

This implements the multi-agent pattern using basic Python libraries:
- Supervisor Agent: Expands queries and coordinates research
- PubMed Researcher: Uses proven search_pubmed and read_pubmed tools
- Direct Bedrock API calls instead of Strands SDK
"""

import json
import boto3
import logging
from typing import Any, Dict, List, Optional
import search_pubmed_simple
import read_pubmed_simple

# Configuration
BEDROCK_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
MAX_SUMMARY_TOKENS = 1000  # Limit for summary generation
TARGET_SUMMARY_LENGTH = 2000  # Target character count for summaries

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Bedrock client
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-2')

def handler(event: Dict[str, Any], context) -> str:
    """
    Main handler implementing the Supervisor Agent pattern without Strands SDK.
    """
    logger.info(f"Event received: {json.dumps(event)}")
    
    user_prompt = event.get("prompt", "")
    if not user_prompt:
        return "Error: No prompt provided"
    
    try:
        # Supervisor Agent analyzes and expands the query
        expanded_query = expand_scientific_query(user_prompt)
        logger.info(f"Expanded query: {expanded_query}")
        
        # Delegate to PubMed Researcher Agent
        research_results = conduct_pubmed_research(expanded_query)
        
        # Supervisor synthesizes the final response
        final_response = synthesize_research_response(user_prompt, research_results)
        
        return final_response
        
    except Exception as e:
        logger.error(f"Error in supervisor handler: {str(e)}")
        return f"Error processing request: {str(e)}"


def expand_scientific_query(user_query: str) -> Dict[str, Any]:
    """
    Supervisor Agent function: Expand user query with scientific inference.
    """
    expansion_prompt = f"""
You are a scientific literature research supervisor. Analyze this user query and expand it with relevant scientific terms, synonyms, and related concepts for comprehensive PubMed searching.

User Query: "{user_query}"

Provide:
1. Expanded search terms (including MeSH terms, synonyms, related concepts)
2. Suggested search strategy (recent papers, reviews, clinical trials, etc.)
3. Key aspects to focus on in the research

Respond in JSON format:
{{
    "expanded_terms": "expanded search query with OR operators",
    "search_strategy": "description of search approach",
    "focus_areas": ["area1", "area2", "area3"],
    "temporal_filter": "time range if relevant (e.g., 'last 5 years')"
}}
"""
    
    try:
        response = call_bedrock_model(expansion_prompt, max_tokens=500)
        # Try to parse as JSON, fallback to simple expansion if parsing fails
        try:
            expansion_data = json.loads(response)
            return expansion_data
        except json.JSONDecodeError:
            # Fallback: create simple expansion
            return {
                "expanded_terms": f"{user_query} OR related terms OR recent advances",
                "search_strategy": "Search for recent literature and reviews",
                "focus_areas": ["recent research", "clinical applications", "mechanisms"],
                "temporal_filter": "last 5 years"
            }
    except Exception as e:
        logger.warning(f"Query expansion failed, using original query: {e}")
        return {
            "expanded_terms": user_query,
            "search_strategy": "Basic search",
            "focus_areas": ["general research"],
            "temporal_filter": None
        }


def conduct_pubmed_research(expansion_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    PubMed Researcher Agent function: Execute literature search and analysis.
    """
    expanded_query = expansion_data.get("expanded_terms", "")
    temporal_filter = expansion_data.get("temporal_filter")
    
    # Add temporal filter if specified
    if temporal_filter and "year" in temporal_filter.lower():
        search_query = f"{expanded_query} AND {temporal_filter}[dp]"
    else:
        search_query = expanded_query
    
    logger.info(f"Executing PubMed search: {search_query}")
    
    try:
        # Use the simplified search_pubmed tool
        search_results = search_pubmed_simple.search_pubmed(
            query=search_query,
            max_results=200,  # Cast wide net
            max_records=20,   # Focus on top results
            rerank="referenced_by"  # Prioritize influential papers
        )
        
        # Extract PMC IDs from search results for full-text reading
        pmc_ids = extract_pmc_ids_from_search(search_results)
        
        # Read 2-3 most relevant articles for detailed analysis
        full_text_analyses = []
        for pmc_id in pmc_ids[:3]:  # Limit to top 3
            try:
                article_content = read_pubmed_simple.read_pubmed(pmcid=pmc_id)
                full_text_analyses.append({
                    "pmcid": pmc_id,
                    "content": article_content
                })
            except Exception as e:
                logger.warning(f"Failed to read {pmc_id}: {e}")
                continue
        
        return {
            "search_results": search_results,
            "full_text_analyses": full_text_analyses,
            "search_query": search_query
        }
        
    except Exception as e:
        logger.error(f"PubMed research failed: {e}")
        return {
            "search_results": f"Search failed: {str(e)}",
            "full_text_analyses": [],
            "search_query": search_query
        }


def extract_pmc_ids_from_search(search_results: str) -> List[str]:
    """
    Extract PMC IDs from search results for full-text reading.
    """
    pmc_ids = []
    lines = search_results.split('\n')
    
    for line in lines:
        # Look for PMC IDs in the search results
        if 'PMC' in line:
            # Simple regex-like extraction
            words = line.split()
            for word in words:
                if word.startswith('PMC') and word[3:].isdigit():
                    pmc_ids.append(word)
                    break
    
    return pmc_ids[:5]  # Return up to 5 PMC IDs


def synthesize_research_response(original_query: str, research_data: Dict[str, Any]) -> str:
    """
    Supervisor Agent function: Synthesize research findings into comprehensive response.
    """
    synthesis_prompt = f"""
You are a scientific research supervisor synthesizing literature findings. Based on the research conducted, provide a comprehensive, well-cited response to the user's question.

Original User Query: "{original_query}"

Research Data:
- Search Query Used: {research_data.get('search_query', 'N/A')}
- Search Results: {research_data.get('search_results', 'No results')}
- Full-text Analyses: {len(research_data.get('full_text_analyses', []))} articles analyzed

Provide a comprehensive response that:
1. Directly answers the user's question
2. Summarizes key findings from the literature
3. Includes proper citations (PMID/PMC references)
4. Explains clinical significance or research implications
5. Identifies any research gaps or emerging trends
6. Uses appropriate scientific terminology

Format your response professionally as a scientific literature review summary.
"""
    
    try:
        response = call_bedrock_model(synthesis_prompt, max_tokens=2000)
        return response
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        # Fallback response
        return f"""
Based on the literature search for "{original_query}":

Search Results Summary:
{research_data.get('search_results', 'Search results unavailable')}

This represents a multi-agent approach where:
1. Supervisor Agent expanded your query: "{research_data.get('search_query', original_query)}"
2. PubMed Researcher Agent conducted comprehensive literature search
3. Supervisor Agent synthesized findings (synthesis temporarily unavailable due to technical issue)

The search identified relevant literature that can provide insights into your question about {original_query}.
"""


def call_bedrock_model(prompt: str, max_tokens: int = 1000) -> str:
    """
    Direct Bedrock API call without Strands SDK.
    """
    try:
        # Try Claude 3.5 Sonnet first
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
        
    except Exception as e:
        logger.warning(f"Claude 3.5 failed, trying Haiku: {e}")
        
        # Fallback to Claude 3 Haiku
        try:
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            response = bedrock_runtime.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                body=json.dumps(request_body)
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
            
        except Exception as e2:
            logger.error(f"All Bedrock models failed: {e2}")
            raise Exception(f"Bedrock API calls failed: {str(e2)}")


# Alternative entry point for testing
def lambda_handler(event, context):
    """Alternative entry point name for AWS Lambda."""
    return handler(event, context)
