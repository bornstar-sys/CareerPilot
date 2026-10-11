\# 0004: Bounded planning and execution



\## Decision



Implement a small plan-and-execute workflow using the existing

Groq text-generation client, Pydantic validation, and compare\_skills.



The planner chooses one of two actions:

\- clarify: ask for missing information without executing a tool.

\- compare: compare supplied skills and generate an explanation

&#x20; or learning plan.



\## Components



\- planning.py: validated decision models.

\- planner.py: model-generated JSON parsed into AgentPlan.

\- execution.py: input verification and deterministic tool execution.

\- agent.py: orchestration and final response generation.



\## Input verification



Comparison requires independently supplied CompareSkillsInput.

The executor rejects planned arguments that differ from those lists

after input validation. Model-generated arguments must not be reused

as the independent source.



Free-text requests without structured supplied skills can clarify,

but cannot execute a comparison successfully.



\## Execution limits and failures



Clarification uses one generation call and no tools.

Successful comparison uses two generation calls and one tool call.

There are no automatic retries or execution loops.



Invalid plans, mismatched inputs, and tool failures stop the workflow.

Final-generation failure propagates rather than returning success.



\## Local configuration



Run local commands from backend and load settings explicitly:



&#x20;   load\_settings(Path(".env"))



The local .env file contains provider, model, and API key settings.

It must remain untracked. Never include its contents in documentation.



Offline tests use mocks and do not require a real API key.



\## Verification



Offline tests cover plan validation, planner response handling,

tool execution, input mismatch rejection, and orchestration failures.



Live checks demonstrated:

\- faithful extraction of supplied skill lists;

\- correct comparison results and generated learning advice;

\- clarification when skill information is missing.



The final wording instruction was subsequently strengthened.

Its effect has not yet been verified in another live response.



\## Limitations



This is a bounded branching workflow, not an iterative agent loop.

It supports one tool and does not implement persistent memory,

automatic clarification resumption, RAG, or arbitrary task planning.



JSON output is requested through a prompt and validated locally.

Generated advice is not guaranteed to be factually faithful.

Suggested timelines are illustrative, not personalized assessments.

