#!/bin/bash

# Simple script to check if all deployment files are present
# Run this before attempting deployment to ensure everything is in place

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get script directory
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_status "PubMed Multi-Agent System - File Structure Check"
print_status "================================================="
print_status "Script directory: $script_dir"
print_status "Current directory: $(pwd)"

echo ""
print_status "Checking required files..."

# Track missing files
missing_files=()
found_files=()

# Function to check file
check_file() {
    local file_path="$1"
    local description="$2"
    
    if [[ -f "$file_path" ]]; then
        print_success "✓ $description"
        found_files+=("$file_path")
    else
        print_error "✗ $description (missing: $file_path)"
        missing_files+=("$file_path")
    fi
}

# Check Lambda functions
print_status ""
print_status "Lambda Functions:"
check_file "${script_dir}/action_groups/pubmed_researcher/lambda/read_pubmed.py" "Read PubMed Lambda function"
check_file "${script_dir}/action_groups/pubmed_researcher/lambda/search_pubmed.py" "Search PubMed Lambda function"

# Check API schemas
print_status ""
print_status "API Schemas:"
check_file "${script_dir}/action_groups/pubmed_researcher/read_pubmed_schema.json" "Read PubMed API schema"
check_file "${script_dir}/action_groups/pubmed_researcher/search_pubmed_schema.json" "Search PubMed API schema"

# Check CloudFormation templates
print_status ""
print_status "CloudFormation Templates:"
check_file "${script_dir}/pubmed-researcher-agent.yaml" "PubMed Researcher Agent template"
check_file "${script_dir}/pubmed-supervisor-agent.yaml" "PubMed Supervisor Agent template"

# Check deployment scripts
print_status ""
print_status "Deployment Scripts:"
check_file "${script_dir}/deploy.sh" "Native deployment script"
check_file "${script_dir}/docker-deploy.sh" "Docker deployment script"

# Check Docker files
print_status ""
print_status "Docker Configuration:"
check_file "${script_dir}/Dockerfile" "Main Dockerfile"
check_file "${script_dir}/docker-compose.yml" "Docker Compose configuration"
check_file "${script_dir}/requirements-deployment.txt" "Python requirements"

# Check optional files
print_status ""
print_status "Optional Files:"
check_file "${script_dir}/env.example" "Environment variables example"
check_file "${script_dir}/README.md" "Documentation"

# Summary
echo ""
print_status "Summary:"
print_status "========="

if [[ ${#missing_files[@]} -eq 0 ]]; then
    print_success "All required files are present!"
    print_success "Found ${#found_files[@]} files total"
    echo ""
    print_status "You can now proceed with deployment:"
    print_status "  ./docker-deploy.sh deploy    # Docker deployment (recommended)"
    print_status "  ./deploy.sh                  # Native deployment"
else
    print_error "Missing ${#missing_files[@]} required files:"
    for file in "${missing_files[@]}"; do
        echo "  - $file"
    done
    echo ""
    print_error "Please ensure all files are present before attempting deployment"
    echo ""
    print_status "If files are missing, you may need to:"
    print_status "1. Check that you're in the correct directory"
    print_status "2. Verify the complete project structure was copied"
    print_status "3. Re-run the file creation commands from the instructions"
fi

# Show directory structure for debugging
echo ""
print_status "Current directory structure:"
print_status "============================="
if command -v tree >/dev/null 2>&1; then
    tree -L 3 "$script_dir" 2>/dev/null || ls -la "$script_dir"
else
    find "$script_dir" -type f -name "*.py" -o -name "*.json" -o -name "*.yaml" -o -name "*.sh" | sort
fi

exit ${#missing_files[@]}
