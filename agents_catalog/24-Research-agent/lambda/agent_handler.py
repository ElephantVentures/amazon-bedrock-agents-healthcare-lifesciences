from typing import Any, Dict
import read_pubmed
import search_pubmed
from strands import Agent
import boto3
import os

# Define a system prompt
SYSTEM_PROMPT = """You are a life science research assistant. When given a scientific question, follow this process:

1. Use the search_pubmed tool with rerank="referenced_by", max_results to 200-500, and max_records to 20-50 to find highly-cited papers. Search broadly first, then narrow down. Use temporal filters like "last 5 years"[dp] for recent work. 
2. Use read_pubmed on the 1-2 most relevant articles from your search results to gain a better understanding of the space. Focus on highly-cited papers and reviews.
3. Extract and summarize the most relevant clinical findings.
3. Return structured, well-cited information with PMID references.

Key guidelines:
- Always use rerank="referenced_by" in searches to prioritize influential papers.
- Limit searches to 20-50 articles for focused analysis.
- Select articles strategically based on citation count and relevance.
"""

def handler(event: Dict[str, Any], _context) -> str:
    # Debug information
    print(f"AWS_REGION environment variable: {os.environ.get('AWS_REGION', 'Not set')}")
    print(f"AWS_DEFAULT_REGION environment variable: {os.environ.get('AWS_DEFAULT_REGION', 'Not set')}")
    print(f"Lambda function region: {_context.invoked_function_arn.split(':')[3] if _context else 'Unknown'}")
    
    # List available models in this region
    try:
        bedrock_client = boto3.client('bedrock', region_name='us-east-2')
        models = bedrock_client.list_foundation_models()
        anthropic_models = [m for m in models['modelSummaries'] if 'anthropic' in m['modelId']]
        print(f"Available Anthropic models in us-east-2: {[m['modelId'] for m in anthropic_models]}")
        
        # Check specifically for Claude 3.7 Sonnet
        claude_37_available = any('claude-3-7-sonnet' in m['modelId'] for m in anthropic_models)
        print(f"Claude 3.7 Sonnet available: {claude_37_available}")
        
    except Exception as e:
        print(f"Error listing models: {e}")
    
    # Test direct Bedrock access
    try:
        bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-2')
        test_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Hello"}]
        }
        
        response = bedrock_runtime.invoke_model(
            modelId="anthropic.claude-3-7-sonnet-20250219-v1:0",
            body=str(test_body).encode('utf-8')
        )
        print("Direct Bedrock model access successful")
        
    except Exception as e:
        print(f"Direct Bedrock access failed: {e}")
        print(f"Error type: {type(e).__name__}")
    
    # Try creating agent with explicit model (no region parameter)
    try:
        # First try Amazon Nova Pro
        agent = Agent(
            system_prompt=SYSTEM_PROMPT,
            tools=[search_pubmed, read_pubmed],
            model="amazon.nova-pro-v1:0"
        )
        print("Agent created successfully with Amazon Nova Pro")
        
        response = agent(event.get("prompt"))
        return str(response)
        
    except Exception as e:
        print(f"Error with Amazon Nova Pro: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # Try Claude 3.5 Sonnet v2 as fallback
        try:
            agent = Agent(
                system_prompt=SYSTEM_PROMPT,
                tools=[search_pubmed, read_pubmed],
                model="anthropic.claude-3-5-sonnet-20241022-v2:0"
            )
            print("Agent created successfully with Claude 3.5 Sonnet v2")
            
            response = agent(event.get("prompt"))
            return str(response)
            
        except Exception as e2:
            print(f"Error with Claude 3.5 Sonnet v2: {e2}")
            
            # Try Claude 3 Haiku as final fallback
            try:
                agent = Agent(
                    system_prompt=SYSTEM_PROMPT,
                    tools=[search_pubmed, read_pubmed],
                    model="anthropic.claude-3-haiku-20240307-v1:0"
                )
                print("Agent created successfully with Claude 3 Haiku")
                
                response = agent(event.get("prompt"))
                return str(response)
                
            except Exception as e3:
                print(f"Error with Claude 3 Haiku: {e3}")
                return f"All model attempts failed. Last error: {str(e3)}"
