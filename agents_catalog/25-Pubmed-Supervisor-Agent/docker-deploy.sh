#!/bin/bash

# Docker-based deployment wrapper for PubMed Multi-Agent System
# This script provides easy Docker-based deployment with proper environment handling

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
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

# Show usage information
show_usage() {
    echo "Docker-based PubMed Multi-Agent System Deployment"
    echo ""
    echo "Usage:"
    echo "  $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  deploy       Deploy the multi-agent system (default)"
    echo "  validate     Validate AWS credentials and configuration"
    echo "  debug        Run debug checks in container"
    echo "  shell        Start interactive shell in deployment container"
    echo "  build        Build the deployment Docker image"
    echo "  clean        Clean up Docker resources"
    echo ""
    echo "Options:"
    echo "  -e, --env-file FILE    Use specific environment file (default: .env)"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Environment Setup:"
    echo "  1. Copy env.example to .env"
    echo "  2. Fill in required values in .env"
    echo "  3. Run: $0 deploy"
    echo ""
    echo "Examples:"
    echo "  $0 deploy                    # Deploy using .env file"
    echo "  $0 validate                  # Validate configuration"
    echo "  $0 shell                     # Interactive debugging"
    echo "  $0 deploy --env-file prod.env # Use custom env file"
}

# Check if Docker is available and detect architecture
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not available in PATH"
        print_error "Please install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed or not available"
        print_error "Please install Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    # Detect architecture and set appropriate Docker Compose file
    local arch=$(uname -m)
    if [[ "$arch" == "arm64" ]]; then
        print_status "Detected Apple Silicon (ARM64) architecture"
        print_status "Using ARM64-optimized Docker configuration for better performance"
        export DOCKER_COMPOSE_FILE="docker-compose.arm64.yml"
    else
        print_status "Detected x86_64 architecture"
        export DOCKER_COMPOSE_FILE="docker-compose.yml"
    fi
}

# Check if environment file exists
check_env_file() {
    local env_file="$1"
    
    if [ ! -f "$env_file" ]; then
        print_error "Environment file '$env_file' not found"
        print_error "Please create it by copying from env.example:"
        print_error "  cp env.example .env"
        print_error "  # Edit .env with your configuration"
        exit 1
    fi
    
    # Check for required variables
    local required_vars=("BUCKET_NAME" "REGION" "ENVIRONMENT_NAME")
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "$env_file" || grep -q "^${var}=$" "$env_file" || grep -q "^${var}=your-" "$env_file"; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        print_error "Missing or incomplete required variables in $env_file:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        print_error "Please update your environment file with actual values"
        exit 1
    fi
}

# Build Docker image
build_image() {
    print_status "Building PubMed deployment Docker image..."
    
    # Check if we're on Apple Silicon and warn about potential performance
    if [[ $(uname -m) == "arm64" ]]; then
        print_warning "Detected Apple Silicon (ARM64) architecture"
        print_warning "Building x86_64 image for AWS Lambda compatibility"
        print_warning "This may take longer due to emulation"
    fi
    
    # Build with architecture-specific configuration
    if docker-compose -f "$DOCKER_COMPOSE_FILE" build --no-cache pubmed-deployment; then
        print_success "Docker image built successfully"
    else
        print_error "Failed to build Docker image"
        if [[ $(uname -m) == "arm64" ]]; then
            print_error "If build fails on Apple Silicon, try:"
            print_error "1. Enable 'Use Rosetta for x86/amd64 emulation' in Docker Desktop"
            print_error "2. Or use the ARM64-optimized build (already selected)"
        fi
        exit 1
    fi
}

# Deploy using Docker
deploy_with_docker() {
    local env_file="$1"
    
    print_status "Starting Docker-based deployment..."
    print_status "Using environment file: $env_file"
    
    # Set environment file for docker-compose
    export COMPOSE_ENV_FILE="$env_file"
    
    # Run deployment
    if docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$env_file" run --rm pubmed-deployment; then
        print_success "Deployment completed successfully!"
        print_status "Check the output above for agent ARNs and next steps"
    else
        print_error "Deployment failed"
        print_error "Check the logs above for error details"
        exit 1
    fi
}

# Validate configuration
validate_config() {
    local env_file="$1"
    
    print_status "Validating AWS credentials and configuration..."
    
    export COMPOSE_ENV_FILE="$env_file"
    
    if docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$env_file" run --rm pubmed-validator; then
        print_success "Configuration validation successful"
    else
        print_error "Configuration validation failed"
        exit 1
    fi
}

# Start interactive shell
start_shell() {
    local env_file="$1"
    
    print_status "Starting interactive shell in deployment container..."
    print_status "Use this for debugging and manual operations"
    
    export COMPOSE_ENV_FILE="$env_file"
    
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$env_file" run --rm -it pubmed-deployment bash
}

# Run debug checks
debug_environment() {
    local env_file="$1"
    
    print_status "Running debug checks in container..."
    
    export COMPOSE_ENV_FILE="$env_file"
    
    docker-compose -f "$DOCKER_COMPOSE_FILE" --env-file "$env_file" run --rm pubmed-deployment ./debug-docker.sh
}

# Clean up Docker resources
clean_docker() {
    print_status "Cleaning up Docker resources..."
    
    # Stop and remove containers (try both compose files)
    docker-compose -f docker-compose.yml down --remove-orphans 2>/dev/null || true
    docker-compose -f docker-compose.arm64.yml down --remove-orphans 2>/dev/null || true
    
    # Remove images
    docker image rm pubmed-supervisor-agent_pubmed-deployment 2>/dev/null || true
    docker image rm pubmed-supervisor-agent_pubmed-validator 2>/dev/null || true
    
    # Clean up unused resources
    docker system prune -f
    
    print_success "Docker cleanup completed"
}

# Main function
main() {
    local command="deploy"
    local env_file=".env"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            deploy|validate|shell|build|clean)
                command="$1"
                shift
                ;;
            -e|--env-file)
                env_file="$2"
                shift 2
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Check Docker availability
    check_docker
    
    # Handle different commands
    case $command in
        build)
            build_image
            ;;
        clean)
            clean_docker
            ;;
        validate)
            check_env_file "$env_file"
            validate_config "$env_file"
            ;;
        debug)
            check_env_file "$env_file"
            debug_environment "$env_file"
            ;;
        shell)
            check_env_file "$env_file"
            start_shell "$env_file"
            ;;
        deploy)
            check_env_file "$env_file"
            print_status "PubMed Multi-Agent System Docker Deployment"
            print_status "============================================="
            
            # Build image if it doesn't exist
            local image_name="25-pubmed-supervisor-agent_pubmed-deployment"
            if [[ $(uname -m) == "arm64" ]]; then
                image_name="25-pubmed-supervisor-agent_pubmed-deployment"
            fi
            
            if ! docker images | grep -q "$image_name"; then
                build_image
            fi
            
            # Deploy
            deploy_with_docker "$env_file"
            ;;
        *)
            print_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
