import json
import logging
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import re
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for reading PubMed articles - Bedrock Agent format.
    
    Args:
        event: Lambda event from Bedrock Agent
        context: Lambda runtime context
        
    Returns:
        dict: Response in Bedrock Agent format
    """
    logger.info(f"Starting read_pubmed Lambda for event: {json.dumps(event)}")

    try:
        # Extract parameters from Bedrock Agent event structure
        action_group = event["actionGroup"]
        api_path = event["apiPath"]
        parameters = event.get("parameters", [])
        http_method = event["httpMethod"]
        
        # Parse parameters from Bedrock Agent format
        pmcid = None
        source = None
        
        for param in parameters:
            if param["name"] == "pmcid":
                pmcid = param["value"]
            elif param["name"] == "source":
                source = param["value"]

        # Validate required parameters
        if not pmcid:
            response_body = {"application/json": {"body": "Error: PMCID parameter is required"}}
            response_code = 400
        else:
            # Read PMC article
            try:
                article_content = read_pmc_article(pmcid, source)
                response_body = {"application/json": {"body": article_content}}
                response_code = 200
            except Exception as read_error:
                logger.error(f"Error reading PMC article: {read_error}")
                response_body = {"application/json": {"body": f"Error reading PMC article: {str(read_error)}"}}
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
        
        logger.info(f"Returning response with status: {response_code}")
        return api_response

    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {e}")
        
        # Error response in Bedrock Agent format
        error_response_body = {"application/json": {"body": f"Unexpected error: {str(e)}"}}
        action_response = {
            'actionGroup': event.get('actionGroup', 'unknown'),
            'apiPath': event.get('apiPath', '/read_pubmed'),
            'httpMethod': event.get('httpMethod', 'POST'),
            'httpStatusCode': 500,
            'responseBody': error_response_body
        }
        
        return {
            'messageVersion': '1.0', 
            'response': action_response
        }


def read_pmc_article(pmcid: str, source: Optional[str] = None) -> str:
    """
    Read PMC article from S3 Open Access Subset.
    
    Args:
        pmcid: PMC identifier (e.g., 'PMC6033041')
        source: Optional DOI URL for citation
        
    Returns:
        str: Article content or status message
    """
    logger.info(f"Reading PMC article: {pmcid}")
    
    # Validate PMCID format
    if not pmcid.startswith('PMC') or not pmcid[3:].isdigit():
        raise ValueError(f"Invalid PMCID format: {pmcid}. Expected format: PMC followed by digits (e.g., PMC6033041)")
    
    # PMC Open Access Subset is available on S3
    # Bucket: pmc-oa-opendata
    # Structure: oa_comm/xml/all/{pmcid}.xml
    
    bucket_name = "pmc-oa-opendata"
    object_key = f"oa_comm/xml/all/{pmcid}.xml"
    
    try:
        # Create S3 client with anonymous access
        s3_client = boto3.client(
            's3',
            config=boto3.session.Config(signature_version='UNSIGNED')
        )
        
        logger.info(f"Attempting to download from s3://{bucket_name}/{object_key}")
        
        # Download the file
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        xml_content = response['Body'].read().decode('utf-8')
        
        logger.info(f"Successfully downloaded {pmcid}, content length: {len(xml_content)}")
        
        # Extract and clean the article content
        article_text = extract_article_text(xml_content)
        
        # Summarize if content is too long
        if len(article_text) > 10000:
            article_text = summarize_article(article_text)
        
        # Format response
        citation_url = source if source else f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
        
        result = f"Article: {pmcid}\n"
        result += f"Source: {citation_url}\n\n"
        result += f"Content:\n{article_text}"
        
        return result
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            return f"Article {pmcid} not found in PMC Open Access Subset. This article may not be available for free access or may not exist."
        elif error_code == 'NoSuchBucket':
            return f"PMC Open Access bucket not accessible. Please check AWS configuration."
        else:
            logger.error(f"S3 ClientError: {e}")
            raise Exception(f"Error accessing PMC article: {error_code}")
    
    except NoCredentialsError:
        logger.error("AWS credentials not available for S3 access")
        raise Exception("AWS credentials not configured for S3 access")
    
    except Exception as e:
        logger.error(f"Unexpected error reading PMC article: {e}")
        raise Exception(f"Failed to read PMC article {pmcid}: {str(e)}")


def extract_article_text(xml_content: str) -> str:
    """
    Extract readable text from PMC XML content.
    
    Args:
        xml_content: Raw XML content from PMC
        
    Returns:
        str: Cleaned article text
    """
    try:
        # Simple text extraction - remove XML tags and clean up
        # This is a basic implementation; you might want to use a proper XML parser
        
        # Remove XML tags
        text = re.sub(r'<[^>]+>', ' ', xml_content)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Extract main sections (this is a simplified approach)
        # In a real implementation, you'd parse the XML structure properly
        
        # Look for common section markers
        sections = []
        
        # Try to find abstract
        abstract_match = re.search(r'abstract[:\s]*(.*?)(?:introduction|background|methods|results|conclusion)', text, re.IGNORECASE | re.DOTALL)
        if abstract_match:
            sections.append(f"Abstract: {abstract_match.group(1).strip()[:1000]}...")
        
        # Try to find introduction
        intro_match = re.search(r'introduction[:\s]*(.*?)(?:methods|materials|results|discussion)', text, re.IGNORECASE | re.DOTALL)
        if intro_match:
            sections.append(f"Introduction: {intro_match.group(1).strip()[:1000]}...")
        
        # Try to find conclusion
        conclusion_match = re.search(r'conclusion[:\s]*(.*?)(?:references|acknowledgment|funding)', text, re.IGNORECASE | re.DOTALL)
        if conclusion_match:
            sections.append(f"Conclusion: {conclusion_match.group(1).strip()[:1000]}...")
        
        if sections:
            return "\n\n".join(sections)
        else:
            # Fallback: return first part of the cleaned text
            return text[:3000] + ("..." if len(text) > 3000 else "")
    
    except Exception as e:
        logger.warning(f"Error extracting text from XML: {e}")
        # Fallback: return truncated raw content
        return xml_content[:2000] + ("..." if len(xml_content) > 2000 else "")


def summarize_article(article_text: str) -> str:
    """
    Summarize article content if it's too long.
    
    Args:
        article_text: Full article text
        
    Returns:
        str: Summarized text
    """
    try:
        # Try to use Amazon Bedrock for summarization
        bedrock_client = boto3.client('bedrock-runtime')
        
        prompt = f"""Please provide a concise summary of this scientific article, focusing on the main findings, methodology, and conclusions:

{article_text[:8000]}

Summary:"""

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())
        summary = response_body['content'][0]['text']
        
        return f"AI Summary:\n{summary}\n\n[Note: This is an AI-generated summary of the full article]"
        
    except Exception as e:
        logger.warning(f"Bedrock summarization failed: {e}")
        
        # Fallback: simple truncation with key sections
        lines = article_text.split('\n')
        important_lines = []
        
        for line in lines[:100]:  # First 100 lines
            line = line.strip()
            if line and (
                any(keyword in line.lower() for keyword in ['abstract', 'conclusion', 'result', 'finding', 'method']) or
                len(line) > 50
            ):
                important_lines.append(line)
                if len(important_lines) >= 20:
                    break
        
        fallback_summary = '\n'.join(important_lines)
        return f"Article Summary (first key sections):\n{fallback_summary}\n\n[Note: Full article content was truncated]"
