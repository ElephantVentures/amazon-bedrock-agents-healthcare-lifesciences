# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dataclasses import dataclass
import json
import logging
import re
from strands import tool
from typing import Optional

logger = logging.getLogger("read_pubmed")

CONTENT_CHARACTER_LIMIT = 100000

# Note: Logging configuration is handled by the main application

# Bedrock configuration for content summarization
BEDROCK_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
MAX_SUMMARY_TOKENS = 5000  # Limit for summary generation
TARGET_SUMMARY_LENGTH = 10000  # Target character count for summaries


class PMCError(Exception):
    """Base exception for PMC-related errors"""

    pass


class PMCValidationError(PMCError):
    """Invalid PMCID format"""

    pass


class PMCSourceValidationError(PMCError):
    """Invalid source URL format"""

    pass


class PMCS3Error(PMCError):
    """S3 access or download error"""

    pass


@dataclass
class PMCArticleResponse:
    """Response model for PMC article retrieval"""

    status: str
    content: Optional[str]
    message: str
    pmcid: str
    license_type: Optional[str]
    s3_path: Optional[str]
    source: Optional[str] = None

    def __post_init__(self):
        """Validate response structure after initialization"""
        self._validate_response()

    def _validate_response(self):
        """Validate response structure and values"""
        # Validate status values
        valid_statuses = {"success", "licensing_restriction", "not_found", "error"}
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{self.status}'. Must be one of: {valid_statuses}"
            )

        # Validate license_type values
        if self.license_type is not None:
            valid_license_types = {"commercial", "non_commercial"}
            if self.license_type not in valid_license_types:
                raise ValueError(
                    f"Invalid license_type '{self.license_type}'. Must be one of: {valid_license_types}"
                )

        # Validate required fields
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Message must be a non-empty string")

        # PMCID validation is more lenient for error responses to handle invalid input
        if self.pmcid is None:
            # Allow None for error responses when user provides None
            if self.status not in {"error", "not_found"}:
                raise ValueError("PMCID cannot be None for non-error responses")
        elif not isinstance(self.pmcid, str):
            raise ValueError("PMCID must be a string or None")
        elif (
            isinstance(self.pmcid, str)
            and not self.pmcid.strip()
            and self.status not in {"error", "not_found"}
        ):
            raise ValueError("PMCID cannot be empty for non-error responses")

        # Validate business logic constraints
        if self.status == "success":
            if self.content is None or not isinstance(self.content, str):
                raise ValueError("Success responses must include content")
            if self.license_type != "commercial":
                raise ValueError("Success responses must have commercial license_type")
            if not self.s3_path:
                raise ValueError("Success responses must include s3_path")

        elif self.status == "licensing_restriction":
            if self.content is not None:
                raise ValueError(
                    "Licensing restriction responses must not include content"
                )
            if self.license_type != "non_commercial":
                raise ValueError(
                    "Licensing restriction responses must have non_commercial license_type"
                )
            if not self.s3_path:
                raise ValueError("Licensing restriction responses must include s3_path")

        elif self.status in {"not_found", "error"}:
            if self.content is not None:
                raise ValueError("Error responses must not include content")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        result = {
            "status": self.status,
            "content": self.content,
            "message": self.message,
            "pmcid": self.pmcid,
            "license_type": self.license_type,
            "s3_path": self.s3_path,
        }

        # Add new standardized fields for generate_report compatibility
        # 'text' field contains the summarized content (Requirements 1.3)
        if self.content is not None:
            result["text"] = self.content

        # 'source' field contains the DOI URL (Requirements 1.4, 2.2)
        if self.source is not None:
            result["source"] = self.source

        return result


def _validate_pmcid(pmcid: str) -> bool:
    """
    Validate PMCID format.

    Args:
        pmcid: PMC identifier to validate

    Returns:
        bool: True if valid, False otherwise
    """
    if not pmcid or not isinstance(pmcid, str):
        return False

    # PMC IDs should start with "PMC" followed by digits
    pattern = r"^PMC\d+$"
    return bool(re.match(pattern, pmcid.strip()))


def _validate_source_url(source: str) -> bool:
    """
    Validate source URL format.

    Args:
        source: URL to validate

    Returns:
        bool: True if valid, False otherwise
    """
    if not source or not isinstance(source, str):
        return False

    # Basic URL validation - should start with http:// or https://
    url_pattern = r"^https?://[^\s/$.?#].[^\s]*$"
    return bool(re.match(url_pattern, source.strip()))


def _format_validation_error_message(pmcid: str) -> str:
    """
    Format validation error message for invalid PMCID.

    Args:
        pmcid: The invalid PMCID

    Returns:
        str: Formatted error message
    """
    return (
        f"Invalid PMCID format: '{pmcid}'. "
        "PMCID must start with 'PMC' followed by digits (e.g., 'PMC6033041')."
    )


def _format_source_validation_error_message(source: str) -> str:
    """
    Format validation error message for invalid source URL.

    Args:
        source: The invalid source URL

    Returns:
        str: Formatted error message
    """
    return (
        f"Invalid source URL format: '{source}'. "
        "Source must be a valid HTTP or HTTPS URL."
    )


@tool
def read_pubmed(pmcid: str, source: str = None) -> dict:
    """
    Retrieve full text of PMC article from S3.

    Args:
        pmcid: PMC identifier (e.g., "PMC6033041")
        source: Optional DOI URL to include in the response for citation purposes

    Returns:
        dict: Object with "source" (DOI/URL) and "text" (content/summary) keys
    """
    logger.info(f"Starting read_pubmed for PMCID: {pmcid}")

    try:
        # Step 1: Validate PMCID format
        if not _validate_pmcid(pmcid):
            logger.warning(f"Invalid PMCID format: {pmcid}")
            raise PMCValidationError(_format_validation_error_message(pmcid))

        # Step 2: Validate source parameter if provided
        if source is not None and not _validate_source_url(source):
            logger.warning(f"Invalid source URL format: {source}")
            raise PMCSourceValidationError(_format_source_validation_error_message(source))

        # Step 3: Retrieve article from S3
        logger.info(f"Retrieving article content for PMCID: {pmcid}")
        response = _retrieve_pmc_article(pmcid, source)

        # Step 4: Return the response as a dictionary
        result_dict = response.to_dict()
        logger.info(f"Successfully processed PMCID: {pmcid}, status: {response.status}")

        return result_dict

    except (PMCValidationError, PMCSourceValidationError) as validation_error:
        # Handle validation errors with structured response
        logger.error(f"Validation error for PMCID {pmcid}: {validation_error}")
        error_response = PMCArticleResponse(
            status="error",
            content=None,
            message=str(validation_error),
            pmcid=pmcid or "invalid",
            license_type=None,
            s3_path=None,
            source=source,
        )
        return error_response.to_dict()

    except PMCS3Error as s3_error:
        # Handle S3-specific errors
        logger.error(f"S3 error for PMCID {pmcid}: {s3_error}")
        error_response = PMCArticleResponse(
            status="error",
            content=None,
            message=f"S3 access error: {str(s3_error)}",
            pmcid=pmcid,
            license_type=None,
            s3_path=None,
            source=source,
        )
        return error_response.to_dict()

    except Exception as unexpected_error:
        # Handle any other unexpected errors
        logger.error(f"Unexpected error for PMCID {pmcid}: {unexpected_error}")
        error_response = PMCArticleResponse(
            status="error",
            content=None,
            message=f"Unexpected error: {str(unexpected_error)}",
            pmcid=pmcid or "unknown",
            license_type=None,
            s3_path=None,
            source=source,
        )
        return error_response.to_dict()


def _retrieve_pmc_article(pmcid: str, source: str = None) -> PMCArticleResponse:
    """
    Retrieve PMC article from S3 bucket.

    Args:
        pmcid: PMC identifier
        source: Optional source URL for citation

    Returns:
        PMCArticleResponse: Structured response with article data

    Raises:
        PMCS3Error: If S3 operations fail
        PMCError: If article processing fails
    """
    try:
        # Initialize S3 client
        s3_client = boto3.client("s3")
        bucket_name = "pmc-oa-opendata"

        # Construct S3 path for the article
        s3_path = f"oa_comm/xml/all/{pmcid}.xml"

        logger.info(f"Attempting to retrieve {s3_path} from bucket {bucket_name}")

        # Check if object exists and get metadata
        try:
            head_response = s3_client.head_object(Bucket=bucket_name, Key=s3_path)
            logger.info(f"Object found: {s3_path}, size: {head_response.get('ContentLength', 'unknown')}")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                logger.warning(f"Article not found in S3: {s3_path}")
                return PMCArticleResponse(
                    status="not_found",
                    content=None,
                    message=f"Article {pmcid} not found in PMC Open Access dataset",
                    pmcid=pmcid,
                    license_type=None,
                    s3_path=s3_path,
                    source=source,
                )
            else:
                logger.error(f"S3 head_object error for {s3_path}: {e}")
                raise PMCS3Error(f"S3 access error: {str(e)}")

        # Download the article content
        try:
            get_response = s3_client.get_object(Bucket=bucket_name, Key=s3_path)
            raw_content = get_response["Body"].read().decode("utf-8")
            logger.info(f"Successfully downloaded {len(raw_content)} characters from {s3_path}")
        except ClientError as e:
            logger.error(f"S3 get_object error for {s3_path}: {e}")
            raise PMCS3Error(f"Failed to download article: {str(e)}")
        except UnicodeDecodeError as decode_error:
            logger.error(f"Unicode decode error for {s3_path}: {decode_error}")
            raise PMCS3Error(f"Failed to decode article content: {str(decode_error)}")

        # Check license and process content
        license_type = _determine_license_type(raw_content)
        logger.info(f"Determined license type: {license_type}")

        if license_type == "commercial":
            # Process content for commercial use
            processed_content = _process_article_content(raw_content, pmcid)
            return PMCArticleResponse(
                status="success",
                content=processed_content,
                message=f"Successfully retrieved and processed article {pmcid}",
                pmcid=pmcid,
                license_type=license_type,
                s3_path=s3_path,
                source=source,
            )
        else:
            # Non-commercial license - return licensing restriction
            return PMCArticleResponse(
                status="licensing_restriction",
                content=None,
                message=f"Article {pmcid} has non-commercial license restrictions",
                pmcid=pmcid,
                license_type=license_type,
                s3_path=s3_path,
                source=source,
            )

    except NoCredentialsError as cred_error:
        logger.error(f"AWS credentials error: {cred_error}")
        raise PMCS3Error(f"AWS credentials not configured: {str(cred_error)}")

    except Exception as e:
        logger.error(f"Unexpected error in _retrieve_pmc_article: {e}")
        raise PMCS3Error(f"Unexpected S3 operation error: {str(e)}")


def _determine_license_type(content: str) -> str:
    """
    Determine license type from article content.

    Args:
        content: Raw XML content of the article

    Returns:
        str: "commercial" or "non_commercial"
    """
    # Look for Creative Commons license indicators
    commercial_indicators = [
        "cc0",
        "cc by",
        "creative commons attribution",
        "public domain",
    ]

    content_lower = content.lower()

    # Check for commercial-friendly licenses
    for indicator in commercial_indicators:
        if indicator in content_lower:
            logger.info(f"Found commercial license indicator: {indicator}")
            return "commercial"

    # Default to non-commercial if no clear commercial license found
    logger.info("No commercial license indicators found, defaulting to non-commercial")
    return "non_commercial"


def _process_article_content(content: str, pmcid: str) -> str:
    """
    Process and summarize article content.

    Args:
        content: Raw XML content
        pmcid: PMC identifier for logging

    Returns:
        str: Processed and summarized content
    """
    try:
        # Extract text content from XML
        extracted_text = _extract_text_from_xml(content)

        # Check content length and summarize if needed
        if len(extracted_text) > CONTENT_CHARACTER_LIMIT:
            logger.info(f"Content too long ({len(extracted_text)} chars), summarizing...")
            summarized_content = _summarize_content(extracted_text, pmcid)
            return summarized_content
        else:
            logger.info(f"Content within limit ({len(extracted_text)} chars), returning as-is")
            return extracted_text

    except Exception as e:
        logger.error(f"Error processing content for {pmcid}: {e}")
        # Return a basic error message rather than failing completely
        return f"Error processing article content: {str(e)}"


def _extract_text_from_xml(xml_content: str) -> str:
    """
    Extract readable text from XML content.

    Args:
        xml_content: Raw XML content

    Returns:
        str: Extracted text content
    """
    try:
        # Use defusedxml for secure XML parsing
        from defusedxml import ElementTree as ET

        # Parse the XML
        root = ET.fromstring(xml_content)

        # Extract text from relevant sections
        text_parts = []

        # Extract title
        title_elements = root.findall(".//article-title")
        for title in title_elements:
            if title.text:
                text_parts.append(f"Title: {title.text.strip()}")

        # Extract abstract
        abstract_elements = root.findall(".//abstract")
        for abstract in abstract_elements:
            abstract_text = "".join(abstract.itertext()).strip()
            if abstract_text:
                text_parts.append(f"Abstract: {abstract_text}")

        # Extract body text
        body_elements = root.findall(".//body")
        for body in body_elements:
            body_text = "".join(body.itertext()).strip()
            if body_text:
                text_parts.append(f"Content: {body_text}")

        # Combine all text parts
        combined_text = "\n\n".join(text_parts)

        if not combined_text.strip():
            return "No readable text content found in article"

        return combined_text

    except ET.ParseError as parse_error:
        logger.error(f"XML parsing error: {parse_error}")
        return f"Error parsing XML content: {str(parse_error)}"
    except Exception as e:
        logger.error(f"Unexpected error extracting text: {e}")
        return f"Error extracting text from article: {str(e)}"


def _summarize_content(content: str, pmcid: str) -> str:
    """
    Summarize content using Amazon Bedrock.

    Args:
        content: Full text content to summarize
        pmcid: PMC identifier for logging

    Returns:
        str: Summarized content
    """
    try:
        # Initialize Bedrock client
        bedrock_client = boto3.client("bedrock-runtime")

        # Prepare summarization prompt
        prompt = f"""Please provide a comprehensive summary of this scientific article. Focus on:
1. Main research objectives and hypotheses
2. Key methodologies used
3. Primary findings and results
4. Clinical or research implications
5. Conclusions and future directions

Article content:
{content[:50000]}  # Limit input to avoid token limits

Provide a detailed but concise summary suitable for research purposes."""

        # Prepare request body for Claude
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": MAX_SUMMARY_TOKENS,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        # Call Bedrock model
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(request_body)
        )

        # Parse response
        response_body = json.loads(response["body"].read())
        summary = response_body["content"][0]["text"]

        logger.info(f"Successfully summarized content for {pmcid}")
        return summary

    except ClientError as bedrock_error:
        logger.error(f"Bedrock error summarizing {pmcid}: {bedrock_error}")
        # Fallback to truncated content
        return content[:TARGET_SUMMARY_LENGTH] + "... [Content truncated due to summarization error]"

    except Exception as e:
        logger.error(f"Unexpected error summarizing {pmcid}: {e}")
        # Fallback to truncated content
        return content[:TARGET_SUMMARY_LENGTH] + "... [Content truncated due to error]"