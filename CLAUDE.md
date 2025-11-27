# Claude Documentation: Legal Risk Analysis System

## Overview

This is an AI-powered legal risk analysis system that performs automated due diligence on corporate data rooms. The system uses the **deepagents framework** to orchestrate a hierarchical architecture of specialized AI agents that work together to analyze legal documents and generate comprehensive risk assessment reports.

## System Architecture

### Core Components

1. **Main Application** (`main_application.py`)
   - Entry point for running complete legal risk analysis workflows
   - Orchestrates the end-to-end process from data room intake to final report delivery
   - Manages the human-in-the-loop approval workflow
   - Extracts generated files from checkpoint state

2. **Agent Configuration** (`agent_configuration.py`)
   - Defines the hierarchical agent architecture using `create_deep_agent`
   - Configures three specialized agents:
     - **Main Coordinating Agent**: Strategic planning and delegation
     - **Legal Analysis Specialist**: Detailed domain-specific analysis
     - **Report Formatter**: Professional report generation
   - Sets up human-in-the-loop interrupts for critical operations

3. **Data Room Tools** (`data_room_tools.py`)
   - Provides tiered access to legal documents:
     - `list_data_room_documents()`: High-level document inventory
     - `get_documents()`: Page-by-page summaries
     - `get_page_text()`: Unlimited text extraction
     - `get_page_image()`: Limited visual examination (50 page limit)

4. **Web Research Tools** (`web_research_tools.py`)
   - `web_search()`: Search for external legal sources
   - `web_fetch()`: Retrieve content from authoritative sources (limited to 20 fetches)

5. **Approval Workflow** (`approval_workflow.py`)
   - Implements human-in-the-loop approval mechanism
   - Handles interrupts for sensitive operations
   - Allows human review and modification of agent decisions

6. **File Extraction** (`file_extraction.py`)
   - Extracts files from LangGraph checkpoint state
   - Organizes outputs by category (reports, findings, research)
   - Provides helpful summaries of extracted content

## Agent Hierarchy

```
Main Coordinating Agent (Strategic Level)
├── Role: Strategic planning, delegation, synthesis
├── Tools: write_todos, task (delegation)
├── Model: Claude Sonnet 4.5
├── Interrupts: write_todos, task
│
├─── Legal Analysis Specialist Subagent
│    ├── Role: Detailed legal risk analysis
│    ├── Tools: All data room tools, web research tools
│    ├── Model: Claude Sonnet 4.5
│    ├── Interrupts: get_documents, web_fetch, write_file, edit_file
│
└─── Report Formatter Subagent
     ├── Role: Professional report generation
     ├── Tools: list_data_room_documents, read_file, write_file
     ├── Model: Claude Sonnet 4.5
     ├── Interrupts: write_file
```

## Workflow

### 1. Strategic Planning Phase
The **Main Coordinating Agent** receives a data room analysis request with document summaries. It:
- Creates a comprehensive analysis plan using `write_todos`
- Identifies relevant legal risk categories (governance, contracts, IP, regulatory, etc.)
- Plans delegation strategy for specialized subagents

### 2. Analytical Execution Phase
For each risk domain, the Main Agent delegates to the **Legal Analysis Specialist**:
- Provides focused task description for specific risk domain
- Specialist navigates documents strategically:
  - Lists available documents
  - Reviews page summaries to identify relevant pages
  - Reads page text (unlimited)
  - Examines page images strategically (limited to 50)
- Specialist performs web research when needed (limited to 20 fetches)
- Specialist documents findings in structured files
- Specialist returns brief summary to Main Agent

### 3. Synthesis Phase
The Main Agent:
- Reviews summaries from all analytical work
- Identifies cross-cutting patterns and themes
- Notes critical issues and interdependencies
- Prepares for final report generation

### 4. Report Generation Phase
The Main Agent delegates to the **Report Formatter** (once):
- Formatter reads all findings files
- Creates professional Word document with:
  - Executive summary
  - Risk findings by category
  - Specific issues with citations
  - Recommendations
- Saves final report as .docx file

### 5. Completion Phase
- System extracts files from checkpoint state to disk
- Organizes outputs by category
- Provides access to final report and supporting materials

## Key Design Principles

### 1. Hierarchical Delegation
- **Main Agent** stays at strategic level, never accesses documents directly
- **Specialist Subagents** handle detailed work in isolated contexts
- This keeps main agent context clean and enables focused analysis

### 2. Progressive Disclosure
Documents are accessed through three tiers:
1. **Document Summaries**: High-level overview (unlimited, no approval)
2. **Page Summaries**: Medium-fidelity page descriptions (requires approval)
3. **Content Access**:
   - Text: Lightweight, unlimited, no approval
   - Images: Heavyweight, limited (50), strategic use only

### 3. Resource Management
- **Unlimited**: Page text retrieval, document listing
- **Limited**: Page images (50), web fetches (20)
- **Strategic**: Use text for reading, images only for visual examination

### 4. Human-in-the-Loop
Critical operations require human approval:
- Main Agent: Analysis strategy (`write_todos`), delegations (`task`)
- Analyst: Document selection, web fetches, file writes
- Formatter: Final report creation

### 5. State Management
- Uses LangGraph checkpointer (MemorySaver) for state persistence
- Each analysis session has unique thread_id
- Files stored in checkpoint state, extracted at completion
- Supports resumption after human approvals

## File Structure

```
/home/user/2811/
├── main_application.py           # Main workflow orchestrator
├── agent_configuration.py        # Agent hierarchy setup
├── data_room_tools.py           # Document access tools
├── web_research_tools.py        # External research tools
├── approval_workflow.py         # Human-in-the-loop system
├── file_extraction.py           # Output extraction utilities
├── legal_preprocessing_v2.py    # Document preprocessing
└── CLAUDE.md                    # This documentation
```

## Usage Example

```python
from main_application import run_legal_risk_analysis

# Run analysis on preprocessed data room
result = run_legal_risk_analysis(
    data_room_path="./preprocessed_data_room",
    output_directory="./analysis_results"
)

# Results include:
# - session_id: Unique identifier for this analysis
# - status: Completion status
# - iterations: Number of approval cycles
# - final_result: Complete LangGraph state
```

## Best Practices

### For Main Coordinating Agent
1. Create comprehensive todo list at start
2. Delegate focused, specific tasks to specialists
3. Don't access documents directly - always delegate
4. Review specialist summaries for synthesis insights
5. Delegate to report formatter only once at the end

### For Legal Analysis Specialist
1. Start by listing all documents to understand landscape
2. Review page summaries before retrieving content
3. Use text retrieval as primary method (unlimited)
4. Reserve image retrieval for visual examination needs
5. Cite all sources precisely (document ID, page number)
6. Write findings to files with clear structure
7. Return concise summary to Main Agent

### For Report Formatter
1. Read all findings files first
2. Organize by risk category
3. Include specific citations for all claims
4. Use professional language and structure
5. Create comprehensive executive summary
6. Save as Word document (.docx)

## Technical Dependencies

- **deepagents**: Hierarchical agent framework
- **LangGraph**: Agent orchestration and state management
- **langchain**: Tool definitions and base framework
- **Claude Sonnet 4.5**: AI model (claude-sonnet-4-5-20250929)

## Risk Categories Typically Analyzed

- Corporate Governance & Compliance
- Commercial Contracts
- Intellectual Property
- Regulatory Compliance
- Employment Matters
- Litigation & Disputes
- Financial Arrangements
- Real Estate Holdings
- Environmental Compliance
- Material Legal Risks

## Output Deliverables

1. **Risk Analysis Report** (Word document)
   - Executive summary
   - Detailed risk findings
   - Evidence citations
   - Severity assessments
   - Recommendations

2. **Supporting Files**
   - Domain-specific findings files
   - Research notes
   - Analysis work products

## Human-in-the-Loop Approval Points

### Main Agent Approvals
- **write_todos**: Review and approve analysis strategy
- **task**: Review and approve each delegation to subagents

### Analyst Approvals
- **get_documents**: Review document selection
- **web_fetch**: Review external source fetches
- **write_file**: Review findings before saving
- **edit_file**: Review edits to existing findings

### Formatter Approvals
- **write_file**: Review final report before saving

## Session Management

Each analysis creates a unique session identified by `thread_id`:
- State persisted in checkpointer
- Supports interruption and resumption
- Files stored in state until extraction
- Session can be resumed after approvals

## Limitations & Constraints

- Maximum 50 page image retrievals per session
- Maximum 20 web fetch operations per session
- Unlimited text page retrievals
- Maximum 50 iterations per analysis (safety limit)
- Human approval required for sensitive operations

## Error Handling

The system includes robust error handling:
- Document/page not found errors
- Image loading errors
- Usage limit exceeded errors
- Checkpoint extraction errors
- Graceful degradation with helpful messages

## Future Enhancements

This architecture is designed to support:
- Additional specialized subagents for specific domains
- Enhanced preprocessing capabilities
- Integration with document management systems
- Expanded web research capabilities
- Multi-format output generation
- Custom risk category configurations

---

**Model**: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
**Framework**: deepagents + LangGraph
**Purpose**: Automated legal due diligence and risk analysis
