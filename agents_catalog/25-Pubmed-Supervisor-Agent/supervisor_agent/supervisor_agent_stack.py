"""
Supervisor Agent CDK Stack

This stack creates:
1. A Lambda layer containing Python dependencies (including Strands SDK)
2. A Lambda function that runs the supervisor agent with PubMed research capabilities
3. IAM permissions for the Lambda to invoke Bedrock APIs and access S3
"""

from pathlib import Path

from aws_cdk import Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from constructs import Construct


class SupervisorAgentStack(Stack):
    """CDK Stack for the Supervisor Agent Lambda function with PubMed research capabilities."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define paths for packaging
        current_dir = Path(__file__).parent.parent
        packaging_dir = current_dir / "packaging"

        zip_dependencies = packaging_dir / "dependencies.zip"
        zip_app = packaging_dir / "app.zip"

        # Create a lambda layer with dependencies (Strands SDK, etc.)
        dependencies_layer = _lambda.LayerVersion(
            self,
            "SupervisorDependenciesLayer",
            code=_lambda.Code.from_asset(str(zip_dependencies)),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Dependencies for Supervisor Agent (httpx, boto3, etc.)",
        )

        # Define the Lambda function
        supervisor_agent_function = _lambda.Function(
            self,
            "SupervisorAgentLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            function_name="SupervisorAgentLambda",
            description="A Supervisor Agent that coordinates PubMed research using multi-agent patterns",
            handler="simple_supervisor_handler.handler",
            code=_lambda.Code.from_asset(str(zip_app)),
            timeout=Duration.seconds(900),  # 15 minutes for complex research tasks
            memory_size=1024,  # More memory for multiple agent coordination
            layers=[dependencies_layer],
            architecture=_lambda.Architecture.ARM_64
        )

        # Add comprehensive permissions for the Lambda function
        supervisor_agent_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=["*"],
            )
        )
        
        # Add S3 permissions for PMC Open Access dataset
        supervisor_agent_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                ],
                resources=[
                    "arn:aws:s3:::pmc-oa-opendata/*"
                ],
            )
        )
        
        # Add permissions for anonymous S3 access (PMC dataset is public)
        supervisor_agent_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:ListBucket",
                ],
                resources=[
                    "arn:aws:s3:::pmc-oa-opendata"
                ],
            )
        )
