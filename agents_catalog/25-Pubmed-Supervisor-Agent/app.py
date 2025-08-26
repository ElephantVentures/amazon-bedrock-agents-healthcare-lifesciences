#!/usr/bin/env python3
"""
Main CDK application entry point for the Supervisor Agent.
"""

import aws_cdk as cdk

from supervisor_agent.supervisor_agent_stack import SupervisorAgentStack


app = cdk.App()
SupervisorAgentStack(app, "SupervisorAgentStack")

app.synth()
