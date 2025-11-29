"""Multi-agent system for handling different types of user queries.

This module contains the orchestrator and specialized agents:
- Orchestrator: Routes queries to appropriate agents
- Visa & Immigration Agent: Handles UK visa and immigration questions
- Housing & Life Support Agent: Covers housing, NHS, GP registration, schools
- Work & Benefits Agent: Employment, NI numbers, benefits
- Fallback General Chat Agent: Handles off-topic or unclear questions
"""