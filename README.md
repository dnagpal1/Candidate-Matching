# AI-driven Hiring Platform

An intelligent, automated matchmaking system for recruiters and job seekers. This platform automates the discovery and matching of candidates to job opportunities using AI agents, semantic extraction, and browser automation.

## Project Overview

The AI-driven Hiring Platform automates and optimizes candidate and job matching by leveraging AI agents, semantic extraction, and browser automation tools. The platform streamlines hiring by eliminating manual search tasks, significantly enhancing efficiency and accuracy for recruiters and job seekers.

## Phase 1: Candidate Discovery (Current Implementation)

This repository contains the implementation of Phase 1, focusing on automated LinkedIn candidate discovery. The implementation follows the Single-Agent Loop Pattern as specified in the PRD.

### Key Features of Phase 1

- **LinkedIn Candidate Search**: Automated searching for candidates on LinkedIn based on job title, location, and other criteria
- **Profile Data Extraction**: Extracting candidate information including name, title, current company, location, and open-to-work status
- **Rate Limiting**: Smart rate limiting to avoid LinkedIn restrictions
- **Background Processing**: Support for long-running background tasks
- **API-First Design**: RESTful API design for all functionality

### Technical Stack

- **FastAPI**: Modern, high-performance web framework for API development
- **Pydantic**: Data validation and settings management
- **Browser Use / Playwright**: Browser automation for LinkedIn interaction
- **PostgreSQL**: Database for candidate data storage
- **Redis**: Caching and task management
- **Docker**: Containerization for easy deployment

## Getting Started

For detailed setup instructions, see [SETUP.md](SETUP.md).

## Project Roadmap

This application is being developed in phases as outlined in the Product Requirements Document below.

---

# Product Requirements Document (PRD)

## 📌 Overview
The AI-driven Hiring Platform automates and optimizes candidate and job matching by leveraging AI agents, semantic extraction, and browser automation tools. The platform streamlines hiring by eliminating manual search tasks, significantly enhancing efficiency and accuracy for recruiters and job seekers.

## 🎯 Product Vision
To create an intelligent, automated matchmaking system that:
- Automates data extraction from LinkedIn.
- Utilizes semantic understanding and machine learning for matching.
- Reduces recruitment time and increases match quality.

## 🔑 Core Features
- Automated candidate and job discovery.
- Semantic data extraction & structuring.
- AI-powered candidate-job matching.
- Automated outreach via personalized messages.
- Robust guardrails and human intervention mechanisms.

## 🗓️ Development Phases with Agent Scaffolding

### Phase 1: Initial Setup & Candidate Discovery (MVP)
- **Pattern**: Single-Agent Loop Pattern
- **Primary Agent**: `CandidateDiscoveryAgent`
- **Tools**:
  - `search_linkedin_candidates`: Navigate to LinkedIn and search using filters.
  - `extract_candidate_profiles`: Scrape name, title, location, current role.
  - `paginate_and_scroll`: Scroll through result pages.
- **Guardrails**:
  - Limit total profiles scraped.
  - Validate presence of core fields (name, role, location).
- **Logic & Flow**:
  - Initialize browser session using [Browser Use](https://github.com/browser-use/browser-use) and Playwright.
  - Trigger `search_linkedin_candidates` based on user-defined input filters.
  - Loop using `paginate_and_scroll` tool until exit condition (e.g., max profiles).
  - For each result, call `extract_candidate_profiles` and run field validation checks.
  - Return structured `CandidateProfile` object.
- **Output Schema**: `CandidateProfile { name, title, location, current_company, skills, open_to_work }`
- **Libraries**: `browser-use`, `playwright`, `pydantic`, `langchain`, `openai`

### Phase 2: Job Discovery & Semantic Extraction
- **Pattern**: Deterministic Flow Pattern
- **Primary Agents**: `JobDiscoveryAgent`, `SemanticExtractionAgent`
- **Tools**:
  - `fetch_job_postings`: Navigate LinkedIn jobs and extract job metadata.
  - `clean_and_format_job_description`: Preprocess text for GPT.
  - `gpt_structure_job`: LLM parses description into JSON schema.
- **Guardrails**:
  - Regex filters for irrelevant jobs.
  - Structured validation of output fields.
- **Logic & Flow**:
  - Use Browser Use to search and extract job listings.
  - Chain extraction + transformation tools deterministically.
  - Apply GPT via OpenAI API to generate structured output.
  - Validate final JSON with Pydantic schema.
- **Output Schema**: `JobPosting { title, company, location, description, skills, urgency_flag }`
- **Libraries**: `openai`, `pydantic`, `browser-use`, `langchain`, `re`

### Phase 3: AI Matching Engine
- **Pattern**: LLM-as-a-Judge Pattern
- **Primary Agents**: `MatchingAgent`, `LLMJudgeAgent`
- **Tools**:
  - `generate_embeddings`: For both candidate and job.
  - `search_similar_jobs`: Pinecone/Weaviate-based similarity lookup.
  - `evaluate_top_matches`: Use GPT to score match quality.
- **Guardrails**:
  - Drop candidates with missing embeddings or empty skill overlap.
  - Ensure scoring justification is well-formed.
- **Logic & Flow**:
  - Extract vector embeddings using OpenAI's `text-embedding-ada-002`.
  - Use Pinecone to query job/candidate vector index.
  - Pass top results to GPT to evaluate contextual fit and generate rationale.
- **Output Schema**: `MatchResult { candidate_id, job_id, match_score, reason }`
- **Libraries**: `openai`, `pinecone-client`, `langchain`, `pydantic`

### Phase 4: Automated Outreach & Interaction
- **Pattern**: Agents as Tools Pattern
- **Primary Agents**: `OutreachManagerAgent`, `MessageComposerAgent`, `MessageSenderAgent`
- **Tools**:
  - `compose_outreach_message`: LLM-generated personalized pitch.
  - `send_linkedin_message`: Trigger Browser Use tool to send message.
  - `track_responses`: Log interactions and reply timestamps.
- **Guardrails**:
  - Message safety filters (no hallucinated job details).
  - Prevent spam to already-contacted candidates.
- **Logic & Flow**:
  - ManagerAgent loops through matched candidates.
  - Calls `compose_outreach_message`, then `send_linkedin_message`.
  - Logs output and waits for feedback asynchronously.
- **Output Schema**: `OutreachLog { candidate_id, message, timestamp, status }`
- **Libraries**: `openai`, `browser-use`, `langchain`, `uuid`, `datetime`

### Phase 5: Full Integration & Compliance
- **Pattern**: Routing & Handoff Pattern
- **Primary Agents**: `TriageAgent`, `ComplianceAgent`, `MonitoringAgent`, `ErrorRecoveryAgent`
- **Tools**:
  - `route_by_risk_type`: Assign issues to appropriate sub-agent.
  - `run_compliance_audit`: Validate scraping activity and outbound volume.
  - `monitor_tool_exceptions`: Record failures, retries, backoff states.
- **Guardrails**:
  - Flag sensitive actions (e.g., excessive scraping volume).
  - Require human approval for risky decisions (e.g., override LinkedIn messaging limits).
- **Logic & Flow**:
  - `TriageAgent` accepts system event and evaluates context.
  - Calls appropriate agent via tool handoff using input parameters.
  - Each agent performs its task and logs outcome.
- **Output Schema**: `SystemHealthEvent { timestamp, agent, risk_type, status, resolution }`
- **Libraries**: `langchain`, `openai`, `logging`, `pydantic`, `uuid`, `sentry-sdk`

## ⚙️ Technical Requirements

### Backend
- Python, FastAPI
- PostgreSQL (structured data), Redis (session management)
- Docker, Kubernetes for containerization and scalability

### Frontend (if applicable)
- React, Next.js, Tailwind CSS

### AI & Semantic Processing
- GPT-4 for semantic parsing and outreach
- OpenAI embeddings, Pinecone/Weaviate for vector matching

### Browser Automation
- Browser Use (powered by Playwright)

### Security & Compliance
- OAuth 2.0, secure credential management
- GDPR & CCPA compliance
- Logging, monitoring, and auditing capabilities
- Robust guardrails (relevance classifiers, safety classifiers, moderation APIs, tool safeguards, rules-based protections, output validation)
- Human intervention workflows for critical and high-risk scenarios

## 🛠️ Development Methodology
- Agile methodology with bi-weekly sprints.
- Continuous integration and continuous deployment (CI/CD).
- Regular code reviews, QA testing, and feedback loops.

## 🚩 Risks & Mitigation
- **Risk**: LinkedIn restrictions or account bans.
  - **Mitigation**: Human-like automation speed, proxy rotation, rate limiting.
- **Risk**: Data privacy violations.
  - **Mitigation**: User consent, encrypted storage, compliance audits.
- **Risk**: Agent misinterpretations or failures.
  - **Mitigation**: Implement clear instructions, robust guardrails, and human-in-the-loop mechanisms for escalations.

## 🗺️ Moat Strategy & Strategic Roadmap

### Phase 6: Proprietary Data Flywheel
- **Goal**: Begin data ownership loop and feedback logging.
- **Tasks**:
  - Add `feedback_agent` to capture recruiter thumbs up/down.
  - Enable resume upload & parsing for candidates.
  - Log candidate interactions and match results to vector DB.
  - Create Pydantic model: `FeedbackEntry { candidate_id, job_id, feedback, timestamp }`
- **Tools**: `record_feedback`, `parse_uploaded_resume`, `store_user_embedding`
- **Outcome**: Enriched user profile DB to support personalized models.

### Phase 7: Network Effects Infrastructure
- **Goal**: Increase collaboration and virality.
- **Tasks**:
  - Build `TeamWorkspaceAgent` for match review across team members.
  - Add social referral agent: `EndorsementTool` for job seekers.
  - Enable internal sharing of top candidates and matches.
- **Outcome**: Recruiters onboard more users through referrals and shared work.

### Phase 8: Personalized Matching Agents
- **Goal**: Train and personalize agents per recruiter/team.
- **Tasks**:
  - Introduce `MemoryAgent` using vector storage for recruiter interactions.
  - Support custom agent instructions per recruiter (stored in DB).
  - Integrate contextual preference memory into `MatchingAgent`.
- **Outcome**: Personalized matching improves with every search.

### Phase 9: Analytics Dashboards & Observability
- **Goal**: Transparency and ROI for hiring teams.
- **Tasks**:
  - Launch dashboards visualizing agent traces, match precision, and time-to-fill.
  - Show conversation-level stats (open rate, reply rate, engagement).
  - Enable retraining requests for underperforming agents.
- **Outcome**: Platform becomes sticky via performance monitoring.

### Phase 10: Community & Trust Layer
- **Goal**: Build brand moat and defensible trust indicators.
- **Tasks**:
  - Launch candidate review system (e.g., "Verified Fit" badges).
  - Implement audit agent to assess JD clarity, fairness, compensation transparency.
  - Roll out `CandidateHub`: resource center + discussion forum + leaderboard.
- **Outcome**: Community participation and job quality standardization.

---

## 🏰 Moat Strategy: Defensibility & Long-Term Value

### 1. Proprietary Data Flywheel
- Capture recruiter feedback on match accuracy (thumbs up/down).
- Enable job seekers to import resumes directly.
- Log behavior signals (views, clicks, response times) to improve ML models.
- Store anonymized structured data to train personalized matching agents.

### 2. Network Effects
- Allow team-based match reviewing and commentary.
- Let recruiters share feedback loops that improve their matching agent.
- Add referral and endorsement mechanisms to attract quality candidates.

### 3. Personalized AI Agents
- Use retrieval-augmented memory for recruiter agents to learn preferences.
- Self-improving agents via feedback loops and fine-tuning.
- Auto-adapt outreach tone, length, and detail to company/candidate style.

### 4. Automation Infrastructure as a Service
- Offer observability dashboards for hiring teams (agent traces, KPIs).
- Allow organizations to fork their own private matching agents.
- Run continual A/B tests on outreach tactics, GPT prompts, and result quality.

### 5. Brand, Community & Trust
- Build a trusted hiring ecosystem with verified companies and job quality badges.
- Launch candidate communities to crowdsource salary transparency and company insights.
- Introduce AI-audited job descriptions and company profiles for standardization.

### What Needs to Change
- Add proprietary data capture into candidate and recruiter workflows.
- Launch MVP dashboards for recruiter-specific agent fine-tuning.
- Embed feedback widgets throughout application and outreach flow.
- Introduce team collaboration tools to rate, comment, or adjust recommendations.
- Offer user-level agent customization and memory.

## 🎖️ Success Metrics
- Reduction in candidate/job discovery time.
- Increased accuracy of matches (feedback loop validation).
- User satisfaction (NPS, qualitative feedback).
- Reduced manual effort and increased automation effectiveness.

---

This PRD provides a clear roadmap and detailed guide for successfully developing your AI-driven hiring platform, informed by best practices from OpenAI's guidelines on building agents and the agent patterns provided in the [OpenAI Agents SDK repository](https://github.com/openai/openai-agents-python/tree/main/examples/agent_patterns).



# Product Requirements Document (PRD)

## 📌 Overview
The AI-driven Hiring Platform automates and optimizes candidate and job matching by leveraging LangGraph-powered AI agents, semantic extraction, and browser automation tools. The platform streamlines hiring by eliminating manual search tasks, significantly enhancing efficiency and accuracy for recruiters and job seekers.

## 🎯 Product Vision
To create an intelligent, autonomous hiring workflow that:
- Automates candidate and job discovery.
- Utilizes semantic understanding and agent memory.
- Matches candidates with roles using explainable, real-time LLM decisioning.
- Continuously improves with feedback and observability.

---

## 🧠 Why LangGraph + Agentic Pattern Selection
LangGraph introduces a powerful agentic architecture using stateful, multi-step agents and node-to-node transitions. This is better suited than linear pipelines or simple tool agents for our use case.

### Patterns Considered
1. **Chain of Tools (linear)** — good for deterministic flows but lacks context reuse or error recovery.
2. **ReAct Loop** — ideal for explorative tasks and real-time reasoning.
3. **Multi-Agent Systems** — powerful but lacks central context/memory retention per agent.
4. **LangGraph DAG + Memory Pattern (Selected)** ✅

### ✅ Why LangGraph DAG + Memory Pattern
- Enables graph-based workflows for phase transitions (e.g., candidate → match → outreach).
- Built-in support for memory (each recruiter’s preferences or candidate history).
- Natural support for guardrails, retries, and conditional logic.
- Each node can be an agent, tool, or evaluator (perfect for modular, extensible design).

---

## 🗓️ Refactored Development Phases Using LangGraph

### Phase 1: Candidate Discovery Graph (Real-Time Intent-Driven)
- **LangGraph Pattern**: DAG + ReAct Loop inside scraping node
- **Human Query Input**: "Find backend engineers in Toronto with Go experience who prefer startups"
- **Graph Nodes**:
  - `ParseIntentNode` → Uses LLM to convert natural query into structured `SearchParameters`
  - `LinkedInPreFilterNode` → Constructs search URL and filters (keywords, location)
  - `GatherProfileLinksNode` → Uses browser to extract 10–15 profile links across pages
  - `ProfileScoringReActNode` → Loops through summary data and reasons which profiles to deep scrape
  - `ProfileExtractorNode` → Scrapes detailed profile for shortlisted candidates
  - `GuardrailValidatorNode` → Ensures schema and relevance validity
- **Memory**: Stores recruiter query, filter context, top-scoring links

### Phase 2: Job Discovery & Semantic Extraction Graph
- **LangGraph Pattern**: Fork-Join Graph
- **Graph Nodes**:
  - `JobScraperNode` → Gathers job listings
  - `DescriptionFormatterNode` → Prepares text
  - `GPTStructurerNode` → Converts to structured JSON
  - `JoinNode` → Passes all job postings to next stage
- **Memory**: Cache industry/job type embeddings

### Phase 3: Matching Engine Graph
- **LangGraph Pattern**: Chain + ReAct Judgment Node
- **Graph Nodes**:
  - `CandidateEmbedderNode`
  - `JobEmbedderNode`
  - `SimilarityMatchNode`
  - `GPTScorerNode` (Judge with rationale)
- **Memory**: Matching history, scores, recruiter intent vectors

### Phase 4: Outreach & Interaction Graph
- **LangGraph Pattern**: Router Node + Parallel Send
- **Graph Nodes**:
  - `MessageComposerNode`
  - `ComplianceFilterNode`
  - `MessageSenderNode`
  - `TrackResponseNode`
- **Memory**: Outreach status, timing, engagement history

### Phase 5: Compliance, Monitoring & Routing Graph
- **LangGraph Pattern**: Handoff & Router
- **Graph Nodes**:
  - `TriageRouterNode`
  - `ComplianceAgentNode`
  - `SystemMonitorNode`
  - `RecoveryEscalationNode`
- **Memory**: Incident history, compliance flags, error traces

---

## ⚙️ Technical Architecture

### Backend
- Python + LangGraph + ReAct agents
- FastAPI, Redis, PostgreSQL
- Pinecone for vector DB
- `browser-use` for real-time scraping (modular tool wrappers)

### Frontend
- Next.js + Tailwind + ShadCN for UI
- Recruiter-facing dashboard

### Tools/Patterns Used
- **ReAct Loop**: for profile pre-screening (phase 1) and matching (phase 3)
- **Agents as Tools**: LinkedIn scraping and scoring agents
- **Memory**: Stored in LangGraph runtime context + Redis cache (for reuse across executions)
- **Guardrails**: Validate input schema, skip malformed pages

---

## 🛡 Guardrails
- Input schema validation from parsed user intent
- Skipping profiles with null fields
- Max scroll/page-depth controls for LinkedIn usage limits
- Bot-detection recovery (e.g., timeout, fallback URL)

---

## 📊 Success Metrics
- Candidate discovery to outreach time < 3 minutes
- Match acceptance rate > 40%
- Personalized agent accuracy improvement with each feedback cycle
- Recruiter retention & NPS scores

---

This updated PRD integrates real-time scraping and reasoning via ReAct, LangGraph memory, and `browser-use`. Each phase is now adaptive to human intent, modular in execution, and efficient in resource use — enabling a truly autonomous hiring workflow.

