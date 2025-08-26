"""
Simplified PubMed Reader - No Strands Dependencies

This is a clean, simplified version of the PubMed article reading functionality
without any Strands framework dependencies.
"""

import boto3
import json
import logging
import re
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional

logger = logging.getLogger(__name__)

def read_pubmed(pmcid: str, source: str = None) -> str:
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
