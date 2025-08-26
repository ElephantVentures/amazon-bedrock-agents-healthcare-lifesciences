from typing import Any, Dict
import search_pubmed
import read_pubmed
from strands import Agent
import boto3
import os

# Define system prompts for both agents
SUPERVISOR_PROMPT = """You are a PubMed Supervisor Agent that coordinates scientific literature research. Your role is to:

1. **Analyze user queries** and expand them with scientific inference to ensure comprehensive search coverage
2. **Delegate to PubMed tools** to gather relevant literature 
3. **Synthesize findings** into well-informed, scientific responses

When a user asks about medical or scientific topics:

1. **Query Expansion**: First, think about related terms, synonyms, and broader/narrower concepts that should be included in the search
2. **Strategic Search**: Use search_pubmed with:
   - Expanded query terms including MeSH terms, synonyms, and related concepts
   - rerank="referenced_by" to prioritize influential papers
   - max_results=200-500 for comprehensive coverage
   - max_records=20-50 for focused analysis
3. **Deep Reading**: Use read_pubmed on 2-3 most relevant articles for detailed insights
4. **Scientific Synthesis**: Provide a comprehensive response that:
   - Summarizes key findings with proper citations
   - Explains clinical significance 
   - Identifies research gaps or emerging trends
   - Uses scientific terminology appropriately

Example query expansion:
- User asks: "cancer biomarkers"
- Expanded search: "cancer biomarkers OR tumor markers OR molecular markers OR prognostic markers OR diagnostic markers OR therapeutic targets"

Always prioritize recent, highly-cited research while including foundational studies when relevant.
"""

PUBMED_RESEARCHER_PROMPT = """You are a specialized PubMed Research Assistant focused on literature search and analysis. You have access to:

1. **search_pubmed**: Search PubMed database with advanced filtering and citation-based ranking
2. **read_pubmed**: Retrieve and summarize full-text articles from PMC Open Access

Guidelines:
- Use rerank="referenced_by" to surface influential papers
- Apply temporal filters like "last 5 years"[dp] for recent research
- Focus on systematic reviews, meta-analyses, and highly-cited original research
- Extract key findings, methodologies, and clinical implications
- Provide proper PMID citations for all referenced work
"""

def handler(event: Dict[str, Any], _context) -> str:
    """
    Main handler that implements the Supervisor Agent pattern.
    The supervisor analyzes queries and delegates to PubMed research tools.
    """
    
    # Debug information
    print(f"AWS_REGION: {os.environ.get('AWS_REGION', 'Not set')}")
    print(f"Lambda region: {_context.invoked_function_arn.split(':')[3] if _context else 'Unknown'}")
    
    user_prompt = event.get("prompt", "")
    print(f"User query: {user_prompt}")
    
    try:
        # Create the Supervisor Agent with PubMed research capabilities
        supervisor_agent = Agent(
            system_prompt=SUPERVISOR_PROMPT,
            tools=[search_pubmed, read_pubmed],
            model="anthropic.claude-3-5-sonnet-20241022-v2:0"  # Using proven model
        )
        
        print("Supervisor Agent created successfully")
        
        # The supervisor agent will:
        # 1. Analyze the user query
        # 2. Expand it with scientific terms
        # 3. Use search_pubmed and read_pubmed tools strategically
        # 4. Synthesize findings into a comprehensive response
        response = supervisor_agent(user_prompt)
        
        return str(response)
        
    except Exception as e:
        print(f"Error with primary model, trying fallback: {e}")
        
        # Fallback to a different model
        try:
            supervisor_agent = Agent(
                system_prompt=SUPERVISOR_PROMPT,
                tools=[search_pubmed, read_pubmed],
                model="anthropic.claude-3-haiku-20240307-v1:0"
            )
            
            print("Supervisor Agent created with fallback model")
            response = supervisor_agent(user_prompt)
            return str(response)
            
        except Exception as e2:
            print(f"Fallback model also failed: {e2}")
            return f"Error: Unable to process request. {str(e2)}"


def create_pubmed_researcher_agent():
    """
    Helper function to create a specialized PubMed Researcher Agent.
    This demonstrates the multi-agent concept within a single Lambda.
    """
    return Agent(
        system_prompt=PUBMED_RESEARCHER_PROMPT,
        tools=[search_pubmed, read_pubmed],
        model="anthropic.claude-3-5-sonnet-20241022-v2:0"
    )


def supervisor_delegate_to_researcher(query: str, researcher_agent: Agent) -> str:
    """
    Example of how the supervisor can delegate specific tasks to the researcher.
    This shows the multi-agent coordination pattern.
    """
    
    # Supervisor expands the query with scientific inference
    expanded_query = f"""
    Research the following topic comprehensively: {query}
    
    Please:
    1. Search for recent literature (last 5 years) 
    2. Include systematic reviews and meta-analyses
    3. Focus on clinical significance and therapeutic implications
    4. Provide detailed citations and summaries
    """
    
    # Delegate to the researcher agent
    researcher_response = researcher_agent(expanded_query)
    
    # Supervisor synthesizes the response
    return f"""
    Based on comprehensive literature analysis:
    
    {researcher_response}
    
    Summary: This research demonstrates the multi-agent coordination where the Supervisor Agent 
    expands queries with scientific inference and delegates to the PubMed Researcher Agent for 
    detailed literature analysis.
    """
