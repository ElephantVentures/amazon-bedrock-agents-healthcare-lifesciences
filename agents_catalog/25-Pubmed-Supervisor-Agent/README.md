# PubMed Multi-Agent System

A sophisticated multi-agent system for comprehensive PubMed literature analysis using Amazon Bedrock. This system consists of two collaborating agents that provide enhanced scientific literature research capabilities.

## Architecture Overview

The system implements a supervisor-subordinate multi-agent architecture:

1. **PubMed Supervisor Agent**: Expands user queries using scientific inference and coordinates research activities
2. **PubMed Researcher Agent**: Executes searches and retrieves articles from PubMed and PMC Open Access Subset

## Key Features

### Scientific Query Expansion
- Automatic identification and inclusion of MeSH terms
- Synonym and alternative terminology expansion
- Temporal filtering capabilities ("last 5 years", etc.)
- Study type filtering (clinical trials, reviews, meta-analyses)
- Multi-faceted query generation for comprehensive coverage

### Citation-Based Ranking
- Results ranked by citation count within the result set
- Prioritization of highly influential papers
- Focus on seminal works in research fields

### Full-Text Access
- Retrieval from PMC Open Access Subset
- Automatic content summarization using Amazon Bedrock
- Proper handling of commercial vs non-commercial licenses
- Intelligent fallback summarization strategies

### Multi-Agent Coordination
- Supervisor maintains conversation context
- Iterative refinement of search strategies
- Synthesis of results from multiple search approaches
- Comprehensive scientific reporting with proper citations

## Components

### PubMed Supervisor Agent
- **Model**: Amazon Nova Pro (with fallbacks)
- **Role**: Query expansion, coordination, and synthesis
- **Capabilities**: Scientific inference, multi-agent coordination, comprehensive reporting

### PubMed Researcher Agent
- **Model**: Amazon Nova Pro (with fallbacks)
- **Role**: Literature search and retrieval
- **Action Groups**:
  - `search_pubmed`: Comprehensive PubMed searches with citation ranking
  - `read_pubmed`: Full-text retrieval from PMC Open Access Subset

### Lambda Functions

#### search_pubmed.py
- Searches PubMed using E-utilities API
- Applies commercial use filtering
- Performs citation analysis and ranking
- Returns formatted results with metadata

#### read_pubmed.py
- Retrieves full-text articles from PMC Open Access S3 bucket
- Handles commercial and non-commercial licensing
- Provides automatic content summarization via Amazon Bedrock
- Includes intelligent fallback summarization

## Deployment

### Prerequisites
- Docker and Docker Compose installed
- AWS credentials configured
- S3 bucket for deployment artifacts
- Amazon Bedrock access with Nova Pro model availability
- (Optional) NCBI API key for enhanced rate limits

### Docker Deployment (Recommended)

Docker deployment resolves environment conflicts and provides a clean, isolated deployment environment.

#### 1. Setup Environment
```bash
# Copy the example environment file
cp env.example .env

# Edit .env with your configuration
nano .env
```

#### 2. Configure Required Variables
Edit `.env` file with your values:
```bash
# Required
BUCKET_NAME=your-deployment-bucket-name
REGION=us-east-1
ENVIRONMENT_NAME=prod
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key

# Optional
BEDROCK_AGENT_SERVICE_ROLE_ARN=arn:aws:iam::account:role/service-role/AmazonBedrockExecutionRoleForAgents_xxx
NCBI_API_KEY=your-ncbi-api-key
```

#### 3. Deploy Using Docker
```bash
# Validate configuration first
./docker-deploy.sh validate

# Deploy the multi-agent system
./docker-deploy.sh deploy
```

#### 4. Docker Deployment Commands
```bash
# Build Docker image
./docker-deploy.sh build

# Deploy with custom environment file
./docker-deploy.sh deploy --env-file prod.env

# Interactive debugging shell
./docker-deploy.sh shell

# Clean up Docker resources
./docker-deploy.sh clean

# Show help
./docker-deploy.sh --help
```

### Native Deployment (Alternative)

For environments without Docker:

#### Environment Variables
```bash
export BUCKET_NAME=your-deployment-bucket
export REGION=us-east-1
export ENVIRONMENT_NAME=prod
export BEDROCK_AGENT_SERVICE_ROLE_ARN=arn:aws:iam::account:role/service-role/AmazonBedrockExecutionRoleForAgents_xxx  # Optional
export NCBI_API_KEY=your-ncbi-api-key  # Optional
```

#### Deploy Both Agents
```bash
./deploy.sh
```

### Deployment Process

Both deployment methods will:
1. Create Python dependencies layer
2. Package and upload Lambda functions
3. Deploy PubMed Researcher Agent with action groups
4. Deploy PubMed Supervisor Agent with collaboration configuration
5. Configure proper IAM permissions and agent aliases

### Troubleshooting Deployment

#### Environment Conflicts
- Use Docker deployment to avoid local environment issues
- Ensure Python 3.12 and pip are available if using native deployment
- Check AWS CLI version compatibility

#### Permission Issues
- Verify AWS credentials have necessary permissions for Bedrock, Lambda, CloudFormation, and S3
- Ensure S3 bucket exists and is accessible
- Check IAM role permissions if providing custom role ARN

#### Docker Issues
```bash
# Check Docker installation
docker --version
docker-compose --version

# Rebuild image if needed
./docker-deploy.sh clean
./docker-deploy.sh build
```

## Usage

### Direct Invocation
Use the Supervisor Agent ARN to invoke the multi-agent system. The Supervisor Agent will automatically coordinate with the Researcher Agent.

### Example Queries
- "What are the latest developments in CRISPR gene editing for cancer treatment?"
- "Find systematic reviews on mRNA vaccine efficacy against COVID-19 variants"
- "Research on biomarkers for early Alzheimer's disease detection in the last 3 years"
- "Clinical trials investigating immunotherapy combinations for melanoma"

### Response Format
Responses include:
1. **Summary**: Brief overview of findings
2. **Key Findings**: Main scientific insights with citations
3. **Methodology**: Types of studies and research approaches
4. **Recent Developments**: Latest research findings
5. **Research Gaps**: Areas needing further investigation
6. **Citations**: Complete reference list with PMIDs and DOIs

## File Structure
```
25-Pubmed-Supervisor-Agent/
├── README.md                           # This file
├── deploy.sh                          # Native deployment script
├── docker-deploy.sh                   # Docker deployment wrapper script
├── Dockerfile                         # Docker image definition
├── docker-compose.yml                 # Docker Compose configuration
├── requirements-deployment.txt        # Python dependencies for deployment
├── env.example                        # Environment variables template
├── .dockerignore                      # Docker ignore file
├── pubmed-researcher-agent.yaml       # CloudFormation template for Researcher Agent
├── pubmed-supervisor-agent.yaml       # CloudFormation template for Supervisor Agent
└── action_groups/
    └── pubmed_researcher/
        ├── lambda/
        │   ├── read_pubmed.py         # Lambda function for article retrieval
        │   └── search_pubmed.py       # Lambda function for PubMed search
        ├── read_pubmed_schema.json    # OpenAPI schema for read function
        └── search_pubmed_schema.json  # OpenAPI schema for search function
```

## Configuration

### Model Selection
The system uses a tiered model approach:
1. **Primary**: Amazon Nova Pro (latest capabilities)
2. **Fallback**: Claude 3.5 Sonnet v2 (reliability)
3. **Final Fallback**: Claude 3 Haiku (cost optimization)

### Search Parameters
- **max_results**: 200-500 (comprehensive initial search)
- **max_records**: 20-50 (focused final results)
- **rerank**: "referenced_by" (citation-based ranking)
- **Commercial filtering**: Enabled by default

### Content Summarization
- **Target length**: ~2000 characters
- **Fallback strategies**: Section extraction, intelligent truncation
- **Model**: Claude 3.5 Sonnet v2 for summarization

## Monitoring and Troubleshooting

### CloudWatch Logs
- Lambda function logs: `/aws/lambda/[stack-name]-[function-name]`
- Agent logs: Available through Bedrock Agent console

### Common Issues
1. **Rate Limiting**: Configure NCBI API key for higher limits
2. **Model Availability**: Ensure Nova Pro is available in your region
3. **S3 Permissions**: Verify anonymous access to PMC Open Access bucket
4. **Agent Collaboration**: Check agent alias ARNs and permissions

## Cost Optimization

### Lambda Functions
- **search_pubmed**: 512MB memory, 5-minute timeout
- **read_pubmed**: 1024MB memory, 15-minute timeout (for summarization)

### Bedrock Usage
- Supervisor Agent: High-quality responses with Nova Pro
- Researcher Agent: Efficient searches and retrieval
- Summarization: Automatic content optimization

## Security Considerations

- Lambda functions use least-privilege IAM roles
- Anonymous S3 access only to PMC Open Access bucket
- No sensitive data stored in Lambda environment
- Optional NCBI API key stored as environment variable

## Future Enhancements

- Integration with additional databases (Scopus, Web of Science)
- Advanced semantic search capabilities
- Real-time literature monitoring and alerts
- Integration with knowledge graphs
- Support for systematic review methodologies
- Custom citation style formatting

## Support and Contributions

This multi-agent system is designed to be extensible and customizable for various scientific research needs. The modular architecture allows for easy addition of new capabilities and integration with other research tools.

For issues or enhancements, refer to the broader Amazon Bedrock Agents Healthcare & Life Sciences repository.
