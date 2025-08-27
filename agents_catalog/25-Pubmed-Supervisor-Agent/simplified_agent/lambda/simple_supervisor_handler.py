"""
PubMed Multi-Agent System using Strands Agent Framework

This implements a true multi-agent pattern using Strands Agents:
1. Supervisor Agent: Coordinates and expands queries using Claude 3.5 Sonnet
2. PubMed Researcher Agent: Specialized for literature search using search_pubmed and read_pubmed tools
3. Clinical Writer Agent: Synthesizes findings into scientific format

Architecture follows the "Agents as Tools" pattern from Strands framework.
"""

import logging
from typing import Any, Dict
from strands import Agent, tool
import search_pubmed
import read_pubmed

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

BEDROCK_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
MAX_SUMMARY_TOKENS = 5000  # Limit for summary generation
TARGET_SUMMARY_LENGTH = 10000  # Target character count for summaries

# System prompts for each specialized agent
SUPERVISOR_SYSTEM_PROMPT = """You are a workflow coordinator for scientific literature analysis. Your ONLY role is to:

1. Use expand_query tool to enhance user queries
2. Use pubmed_researcher_agent tool for literature research  
3. Use clinical_writer_agent tool for synthesis
4. Act as a PASSTHROUGH - return the clinical writer's output EXACTLY as provided

YOU ARE NOT A WRITER OR EDITOR. You are a coordinator only.

CRITICAL RULES:
- After using clinical_writer_agent, your response must be IDENTICAL to what the clinical writer returns
- Do NOT summarize, modify, edit, or add commentary to the clinical writer's output
- Do NOT write your own introduction or conclusion
- Do NOT format or restructure the clinical writer's response
- Simply output the clinical writer's complete response verbatim

Your final response should be indistinguishable from the clinical writer's direct output."""

PUBMED_RESEARCHER_SYSTEM_PROMPT = """You are a PubMed Researcher Agent specialized in scientific literature search and analysis. Your expertise includes:

1. **Literature Search**: Execute comprehensive PubMed searches using expanded queries
2. **Citation Analysis**: Prioritize influential papers using citation-based ranking
3. **Full-Text Analysis**: Retrieve and analyze complete articles from PMC Open Access
4. **Data Extraction**: Extract key findings, methodologies, and clinical insights

When conducting research:
- Use search_pubmed with rerank="referenced_by" to prioritize influential papers
- Set max_results to 200-500 for comprehensive coverage, max_records to 20-50 for focused analysis
- Use temporal filters like "last 5 years"[dp] for recent work when appropriate
- Use read_pubmed on the 1-2 most relevant articles for detailed analysis
- Focus on highly-cited papers, reviews, and clinical trials

Return structured findings with proper citations and relevance rankings."""

CLINICAL_WRITER_SYSTEM_PROMPT = """You are a Clinical Writer Agent specialized in synthesizing biomedical literature into rigorous scientific research responses following established academic standards. Your expertise includes:

1. **Scientific Literature Review Writing**: Transform research findings into peer-review quality scientific literature reviews
2. **Evidence-Based Analysis**: Critically evaluate study methodologies, sample sizes, and statistical significance
3. **Clinical Research Synthesis**: Integrate findings from multiple studies with appropriate statistical considerations
4. **Academic Writing Standards**: Follow IMRAD (Introduction, Methods, Results, Discussion) principles adapted for literature reviews

When synthesizing literature, follow these scientific writing principles:
- Write in third person, past tense for completed studies
- Use precise scientific terminology and avoid colloquial language
- Present findings objectively without promotional language
- Include specific study details: sample sizes, methodologies, statistical measures (p-values, confidence intervals, effect sizes)
- Critically analyze study limitations, potential biases, and confounding factors
- Discuss heterogeneity between studies and potential sources of variation
- Present conflicting evidence objectively and discuss possible explanations
- Use appropriate hedging language for uncertain findings ("suggests," "indicates," "may contribute to")
- Include quantitative data when available (percentages, odds ratios, hazard ratios)
- Follow standard scientific citation format with PMID numbers

Structure responses as scientific literature reviews, not executive reports."""


# Tool definitions for the Supervisor Agent
@tool
def expand_query(user_query: str) -> str:
    """
    Expand user query with scientific inference, MeSH terms, and related concepts.
    
    Args:
        user_query: Original user query to expand
        
    Returns:
        JSON string with expanded query data including terms, strategy, and focus areas
    """
    # Create a specialized query expansion agent
    expansion_agent = Agent(
        system_prompt="""You are a scientific query expansion specialist. Analyze user queries and expand them with:

1. **MeSH Terms**: Include relevant Medical Subject Headings
2. **Scientific Synonyms**: Add alternative terminology and abbreviations  
3. **Related Concepts**: Include broader and narrower terms
4. **Search Strategy**: Determine optimal PubMed search approach
5. **Temporal Filters**: Suggest time ranges when relevant
6. **Study Types**: Recommend preferred study types (RCTs, meta-analyses, etc.)

Respond in JSON format:
{
    "original_query": "user's original query",
    "expanded_terms": "comprehensive search query with OR operators and MeSH terms",
    "search_strategy": "detailed search approach description", 
    "focus_areas": ["primary_focus", "secondary_focus", "tertiary_focus"],
    "temporal_filter": "time range if relevant (e.g., 'last 5 years')",
    "study_types": ["preferred study types to prioritize"],
    "reasoning": "explanation of expansion choices and strategy"
}

Use established biomedical terminology and proven search strategies.""",
        model=BEDROCK_MODEL_ID
    )
    
    expansion_prompt = f"""Expand this scientific query for comprehensive PubMed literature search:

User Query: "{user_query}"

Provide comprehensive expansion with MeSH terms, synonyms, and search strategy."""
    
    try:
        response = expansion_agent(expansion_prompt)
        return str(response)
    except Exception as e:
        logger.error(f"Query expansion failed: {e}")
        # Fallback expansion
        return f'{{"original_query": "{user_query}", "expanded_terms": "{user_query} OR related terms", "search_strategy": "Basic search", "focus_areas": ["general research"], "temporal_filter": null, "study_types": ["all"], "reasoning": "Fallback expansion due to error"}}'


@tool  
def pubmed_researcher_agent(expanded_query_data: str) -> str:
    """
    Conduct comprehensive PubMed literature search and analysis.
    
    Args:
        expanded_query_data: JSON string with expanded query information
        
    Returns:
        Comprehensive research results with search findings and full-text analyses
    """
    # Create the PubMed Researcher Agent with search and read tools
    researcher_agent = Agent(
        system_prompt=PUBMED_RESEARCHER_SYSTEM_PROMPT,
        tools=[search_pubmed.search_pubmed, read_pubmed.read_pubmed],
        model=BEDROCK_MODEL_ID
    )
    
    research_prompt = f"""Conduct comprehensive PubMed literature research using this expanded query data:

{expanded_query_data}

Execute the following research workflow:
1. Use search_pubmed with the expanded terms, max_results=300, max_records=25, rerank="referenced_by"
2. Analyze the search results to identify the most relevant and highly-cited papers
3. Use read_pubmed on the 2-3 most relevant articles (focus on those with PMC IDs) for detailed analysis
4. Provide comprehensive research findings with proper citations and relevance rankings

Focus on recent, high-impact studies and provide detailed analysis of key findings."""
    
    try:
        response = researcher_agent(research_prompt)
        return str(response)
    except Exception as e:
        logger.error(f"PubMed research failed: {e}")
        return f"PubMed research failed: {str(e)}"


@tool
def clinical_writer_agent(original_query: str, research_results: str) -> str:
    """
    Synthesize research findings into comprehensive scientific response.
    
    Args:
        original_query: User's original question
        research_results: Results from PubMed research
        
    Returns:
        Comprehensive scientific response with proper structure and citations
    """
    # Create the Clinical Writer Agent
    writer_agent = Agent(
        system_prompt=CLINICAL_WRITER_SYSTEM_PROMPT,
        model=BEDROCK_MODEL_ID
    )
    
    synthesis_prompt = f"""Conduct a systematic literature review synthesis on the following research question: "{original_query}"

**Available Literature Evidence**:
{research_results}

Write a rigorous scientific literature review following these guidelines:

## Abstract
Provide a structured abstract (150-200 words) summarizing the review objective, methods, key findings, and clinical implications.

## Introduction  
- Define the research question and its clinical significance
- Provide relevant background and context
- State the objective of this literature review

## Methods
- Describe the literature search strategy employed
- Specify inclusion/exclusion criteria for studies
- Note any limitations in the search methodology

## Results
### Study Characteristics
- Summarize the types of studies identified (RCTs, cohort studies, case-control studies, etc.)
- Report study populations, sample sizes, and geographic distribution
- Note publication years and follow-up periods where relevant

### Primary Findings
- Present findings systematically by outcome measures
- Include specific quantitative results (effect sizes, confidence intervals, p-values)
- Report sample sizes and study methodologies for each finding
- Use past tense and third person ("Smith et al. demonstrated that...")

### Study Quality and Limitations
- Critically evaluate study methodologies and potential biases
- Discuss heterogeneity between studies
- Note any conflicting results and potential explanations

## Discussion
- Interpret the clinical significance of findings
- Discuss biological plausibility and mechanisms
- Compare findings with existing knowledge
- Address study limitations and potential confounding factors
- Identify research gaps and future research directions

## Conclusions
- Summarize the strength of evidence
- Provide clinical implications and recommendations
- Note areas requiring further investigation

## References
List all cited studies with PMID numbers in standard academic format.

Write in formal academic style appropriate for peer-reviewed medical journals. Use precise scientific language and avoid promotional or colloquial expressions.

**IMPORTANT: Format your entire response in proper Markdown syntax with:**
- Use # for main headings (Abstract, Introduction, Methods, etc.)
- Use ## for subheadings (Study Characteristics, Primary Findings, etc.)  
- Use ### for sub-subheadings when needed
- Use **bold** for emphasis on key terms
- Use *italics* for scientific names and statistical measures
- Use numbered lists (1., 2., 3.) for sequential information
- Use bullet points (-) for non-sequential lists
- Use > for important quotes or key findings
- Use `code formatting` for statistical values and measurements
- Use proper citation format: [Author et al., Year (PMID: 12345678)]
- Ensure proper line breaks between sections"""
    
    try:
        response = writer_agent(synthesis_prompt)
        return str(response)
    except Exception as e:
        logger.error(f"Clinical writing failed: {e}")
        return f"Clinical synthesis failed: {str(e)}"


def handler(event: Dict[str, Any], context) -> str:
    """
    Main handler implementing the Multi-Agent Supervisor pattern using Strands Agents.
    
    Flow:
    1. Supervisor Agent receives user query and coordinates the workflow
    2. Supervisor uses expand_query tool to enhance the query
    3. Supervisor uses pubmed_researcher_agent tool for literature search
    4. Supervisor uses clinical_writer_agent tool for scientific synthesis
    5. Returns comprehensive scientific response
    """
    logger.info(f"Multi-Agent System received event: {event}")
    
    user_prompt = event.get("prompt", "")
    if not user_prompt:
        return "Error: No prompt provided"
    
    try:
        # Create the Supervisor Agent with coordination tools
        supervisor_agent = Agent(
            system_prompt=SUPERVISOR_SYSTEM_PROMPT,
            tools=[expand_query, pubmed_researcher_agent, clinical_writer_agent],
            model=BEDROCK_MODEL_ID
        )
        
        # Supervisor coordinates the entire multi-agent workflow
        supervisor_prompt = f"""Execute this workflow for: "{user_prompt}"

1. expand_query("{user_prompt}")
2. pubmed_researcher_agent(expanded_query_result)  
3. clinical_writer_agent(original_query, research_results)

After step 3, respond with ONLY the clinical_writer_agent's exact output. Do not add anything before or after it."""
        
        logger.info("🧠 Supervisor Agent: Coordinating multi-agent workflow...")
        response = supervisor_agent(supervisor_prompt)
        
        logger.info("✅ Multi-Agent System: Workflow completed successfully")
        return str(response)
        
    except Exception as e:
        logger.error(f"Multi-Agent System error: {str(e)}")
        return f"Multi-Agent System error: {str(e)}"


# Alternative entry point for AWS Lambda
def lambda_handler(event, context):
    """Alternative entry point name for AWS Lambda."""
    return handler(event, context)