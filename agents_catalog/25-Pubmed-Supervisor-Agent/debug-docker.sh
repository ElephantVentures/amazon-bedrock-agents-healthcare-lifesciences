#!/bin/bash

# Debug script to check Docker environment and file mounting

echo "=== Docker Environment Debug ==="
echo "Current working directory: $(pwd)"
echo "Home directory: $HOME"
echo "User: $(whoami)"
echo "UID: $(id -u)"
echo "GID: $(id -g)"

echo ""
echo "=== Environment Variables ==="
env | grep -E "(AWS|BUCKET|REGION|ENVIRONMENT)" | sort

echo ""
echo "=== File System Check ==="
echo "Root directory contents:"
ls -la / | head -10

echo ""
echo "Workspace directory check:"
if [[ -d "/workspace" ]]; then
    echo "✓ /workspace exists"
    echo "Workspace contents:"
    ls -la /workspace | head -10
    
    echo ""
    echo "Looking for action_groups:"
    if [[ -d "/workspace/action_groups" ]]; then
        echo "✓ action_groups directory found"
        ls -la /workspace/action_groups
        
        if [[ -d "/workspace/action_groups/pubmed_researcher" ]]; then
            echo "✓ pubmed_researcher directory found"
            ls -la /workspace/action_groups/pubmed_researcher
            
            if [[ -d "/workspace/action_groups/pubmed_researcher/lambda" ]]; then
                echo "✓ lambda directory found"
                ls -la /workspace/action_groups/pubmed_researcher/lambda
            else
                echo "✗ lambda directory missing"
            fi
        else
            echo "✗ pubmed_researcher directory missing"
        fi
    else
        echo "✗ action_groups directory missing"
    fi
else
    echo "✗ /workspace does not exist"
fi

echo ""
echo "=== CloudFormation Templates Check ==="
if [[ -f "/workspace/pubmed-researcher-agent.yaml" ]]; then
    echo "✓ pubmed-researcher-agent.yaml found"
else
    echo "✗ pubmed-researcher-agent.yaml missing"
fi

if [[ -f "/workspace/pubmed-supervisor-agent.yaml" ]]; then
    echo "✓ pubmed-supervisor-agent.yaml found"
else
    echo "✗ pubmed-supervisor-agent.yaml missing"
fi

echo ""
echo "=== AWS CLI Check ==="
aws --version
echo "AWS CLI config:"
aws configure list

echo ""
echo "=== Python Environment ==="
python --version
pip --version

echo ""
echo "=== Script Location Check ==="
echo "Script path: $0"
echo "Script directory: $(dirname $0)"
echo "Absolute script directory: $(cd $(dirname $0) && pwd)"
