# Multi-stage build for PubMed Multi-Agent System deployment
FROM --platform=linux/amd64 python:3.12-slim as builder

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    unzip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI v2 with architecture detection
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"; \
    elif [ "$ARCH" = "aarch64" ]; then \
        curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf aws awscliv2.zip

# Create Python virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies for Lambda functions
COPY requirements-deployment.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-deployment.txt

# Production stage
FROM --platform=linux/amd64 python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    zip \
    unzip \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Copy AWS CLI from builder
COPY --from=builder /usr/local/aws-cli/ /usr/local/aws-cli/
COPY --from=builder /usr/local/bin/aws /usr/local/bin/aws

# Copy Python virtual environment
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd -r deploy && useradd -r -g deploy deploy

# Set working directory
WORKDIR /workspace

# Copy deployment files
COPY --chown=deploy:deploy . .

# Make scripts executable
RUN chmod +x deploy.sh

# Switch to non-root user
USER deploy

# Set default environment variables
ENV AWS_DEFAULT_REGION=us-east-1
ENV AWS_PAGER=""
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD aws --version || exit 1

# Default command
CMD ["./deploy.sh"]
