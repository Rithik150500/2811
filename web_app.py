"""
web_app.py

FastAPI web application for the Legal Risk Analysis System.
Provides a user-friendly web interface for running analyses, managing approvals,
and viewing results.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi import Request, Form, UploadFile, File
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import uuid
import json
import asyncio
from pathlib import Path
from datetime import datetime
import shutil

from agent_configuration import legal_analysis_agent, checkpointer
from approval_workflow import approval_handler
from file_extraction import (
    extract_files_from_checkpoint,
    organize_extracted_files,
    print_extraction_summary
)

# Initialize FastAPI app
app = FastAPI(
    title="Legal Risk Analysis System",
    description="AI-powered legal due diligence and risk analysis platform",
    version="1.0.0"
)

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory storage for active sessions
active_sessions: Dict[str, Dict[str, Any]] = {}
websocket_connections: Dict[str, WebSocket] = {}


# Pydantic models for API requests/responses
class AnalysisRequest(BaseModel):
    data_room_path: str
    output_directory: Optional[str] = "./analysis_output"
    analysis_scope: Optional[str] = None


class AnalysisSession(BaseModel):
    session_id: str
    status: str
    created_at: str
    data_room_path: str
    output_directory: str
    current_iteration: int
    pending_approvals: List[Dict] = []


class ApprovalDecision(BaseModel):
    session_id: str
    decisions: List[Dict[str, Any]]


# Helper functions
def get_document_summaries(data_room_path: str) -> List[Dict]:
    """Load document summaries from data room index."""
    try:
        from storage_and_tools import data_room_storage
        return data_room_storage.list_all_documents()
    except Exception as e:
        # Fallback: try to load from index file
        index_path = Path(data_room_path) / "data_room_index.json"
        if index_path.exists():
            with open(index_path, 'r') as f:
                data = json.load(f)
                return data.get('documents', [])
        return []


def create_analysis_request_text(documents: List[Dict], custom_scope: Optional[str] = None) -> str:
    """Create the initial analysis request text."""
    doc_summary_text = "\n\n".join([
        f"Document {doc.get('doc_id', doc.get('document_id'))}: {doc['title']}\n"
        f"Type: {doc['document_type']}\n"
        f"Pages: {doc['page_count']}\n"
        f"Summary: {doc.get('summdesc', doc.get('summary_description'))}"
        for doc in documents
    ])

    scope_text = custom_scope if custom_scope else """Conduct thorough legal due diligence across all relevant risk categories including but not limited to:
- Corporate governance structure and compliance
- Commercial contracts and obligations
- Intellectual property assets and protections
- Regulatory compliance status
- Employment matters
- Litigation and disputes
- Financial arrangements and liabilities
- Real estate holdings
- Environmental compliance
- Any other material legal risks"""

    return f"""Please analyze this corporate data room for legal risks and produce a comprehensive risk analysis report.

DATA ROOM CONTENTS:

{doc_summary_text}

ANALYSIS SCOPE:

{scope_text}

DELIVERABLE:

Produce a professional legal risk analysis report in Word format that:
- Provides an executive summary of key findings
- Details specific risks identified in each category
- Cites supporting evidence from documents
- Assesses severity of each risk
- Offers recommendations for risk mitigation
- Maintains professional quality suitable for decision-makers

Please create your analysis plan, conduct the investigation, and deliver the final report."""


async def send_update(session_id: str, update: Dict):
    """Send real-time update to connected WebSocket client."""
    if session_id in websocket_connections:
        try:
            await websocket_connections[session_id].send_json(update)
        except:
            # Connection closed, remove it
            del websocket_connections[session_id]


# API Routes

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page showing active sessions and new analysis form."""
    sessions = [
        {
            "session_id": sid,
            "status": session["status"],
            "created_at": session["created_at"],
            "data_room_path": session["data_room_path"],
            "current_iteration": session.get("current_iteration", 0)
        }
        for sid, session in active_sessions.items()
    ]

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "sessions": sessions}
    )


@app.get("/session/{session_id}", response_class=HTMLResponse)
async def session_detail(request: Request, session_id: str):
    """Detailed view of a specific analysis session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_id]

    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "session": session,
            "session_id": session_id
        }
    )


@app.post("/api/analysis/start")
async def start_analysis(
    background_tasks: BackgroundTasks,
    data_room_path: str = Form(...),
    output_directory: str = Form("./analysis_output"),
    analysis_scope: Optional[str] = Form(None)
):
    """Start a new legal risk analysis session."""

    # Validate data room path
    if not Path(data_room_path).exists():
        raise HTTPException(status_code=400, detail="Data room path does not exist")

    # Generate session ID
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    # Create output directory
    output_dir = Path(output_directory) / session_id
    output_dir.mkdir(exist_ok=True, parents=True)

    # Initialize session
    active_sessions[session_id] = {
        "session_id": session_id,
        "status": "initializing",
        "created_at": datetime.now().isoformat(),
        "data_room_path": data_room_path,
        "output_directory": str(output_dir),
        "current_iteration": 0,
        "pending_approvals": [],
        "messages": [],
        "config": config
    }

    # Load document summaries
    documents = get_document_summaries(data_room_path)

    # Create initial request
    initial_request = create_analysis_request_text(documents, analysis_scope)

    # Start analysis in background
    background_tasks.add_task(run_analysis_async, session_id, initial_request, config)

    return {
        "session_id": session_id,
        "status": "started",
        "message": "Analysis session started successfully"
    }


async def run_analysis_async(session_id: str, initial_request: str, config: Dict):
    """Run the analysis in the background with approval handling."""

    try:
        session = active_sessions[session_id]
        session["status"] = "running"

        await send_update(session_id, {
            "type": "status",
            "status": "running",
            "message": "Starting analysis..."
        })

        # Invoke the main agent
        result = legal_analysis_agent.invoke(
            {"messages": [{"role": "user", "content": initial_request}]},
            config=config
        )

        # Enter approval loop
        iteration = 0
        max_iterations = 50

        while iteration < max_iterations:
            iteration += 1
            session["current_iteration"] = iteration

            # Check for interrupt
            if approval_handler.check_for_interrupt(result):
                session["status"] = "awaiting_approval"

                # Extract approval requests
                pending_approvals = approval_handler.extract_approval_info(result)
                session["pending_approvals"] = pending_approvals

                await send_update(session_id, {
                    "type": "approval_required",
                    "iteration": iteration,
                    "approvals": pending_approvals
                })

                # Wait for user decisions (they'll come via API)
                # The session will be resumed when user submits approvals
                return

            else:
                # Analysis complete
                session["status"] = "completed"
                session["final_result"] = result

                await send_update(session_id, {
                    "type": "status",
                    "status": "completed",
                    "message": "Analysis completed successfully"
                })

                # Extract files
                await extract_analysis_files(session_id)

                break

        if iteration >= max_iterations:
            session["status"] = "error"
            session["error"] = "Maximum iterations reached"
            await send_update(session_id, {
                "type": "error",
                "message": "Maximum iterations reached"
            })

    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        await send_update(session_id, {
            "type": "error",
            "message": f"Error during analysis: {str(e)}"
        })


async def extract_analysis_files(session_id: str):
    """Extract generated files from checkpoint state."""
    session = active_sessions[session_id]

    try:
        saved_files = extract_files_from_checkpoint(
            config=session["config"],
            checkpointer=checkpointer,
            output_directory=session["output_directory"]
        )

        session["extracted_files"] = saved_files

        await send_update(session_id, {
            "type": "files_extracted",
            "file_count": len(saved_files),
            "files": saved_files
        })

    except Exception as e:
        await send_update(session_id, {
            "type": "warning",
            "message": f"Error extracting files: {str(e)}"
        })


@app.post("/api/approval/submit")
async def submit_approval(
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    decisions_json: str = Form(...)
):
    """Submit approval decisions for a pending session."""

    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_id]

    if session["status"] != "awaiting_approval":
        raise HTTPException(status_code=400, detail="Session is not awaiting approval")

    # Parse decisions
    decisions = json.loads(decisions_json)

    # Resume analysis with decisions
    background_tasks.add_task(resume_analysis_async, session_id, decisions)

    return {
        "status": "resumed",
        "message": "Analysis resumed with approval decisions"
    }


async def resume_analysis_async(session_id: str, decisions: List[Dict]):
    """Resume analysis after approval decisions."""

    session = active_sessions[session_id]
    session["status"] = "running"
    session["pending_approvals"] = []

    await send_update(session_id, {
        "type": "status",
        "status": "running",
        "message": "Resuming analysis..."
    })

    try:
        # Create resume command
        resume_command = approval_handler.create_resume_command(decisions)

        # Continue execution
        result = legal_analysis_agent.invoke(
            resume_command,
            config=session["config"]
        )

        # Continue the approval loop
        iteration = session["current_iteration"]
        max_iterations = 50

        while iteration < max_iterations:
            iteration += 1
            session["current_iteration"] = iteration

            if approval_handler.check_for_interrupt(result):
                session["status"] = "awaiting_approval"
                pending_approvals = approval_handler.extract_approval_info(result)
                session["pending_approvals"] = pending_approvals

                await send_update(session_id, {
                    "type": "approval_required",
                    "iteration": iteration,
                    "approvals": pending_approvals
                })
                return
            else:
                session["status"] = "completed"
                session["final_result"] = result

                await send_update(session_id, {
                    "type": "status",
                    "status": "completed",
                    "message": "Analysis completed successfully"
                })

                await extract_analysis_files(session_id)
                break

    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        await send_update(session_id, {
            "type": "error",
            "message": f"Error during analysis: {str(e)}"
        })


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return active_sessions[session_id]


@app.get("/api/sessions")
async def list_sessions():
    """List all active sessions."""
    return {
        "sessions": [
            {
                "session_id": sid,
                "status": session["status"],
                "created_at": session["created_at"],
                "current_iteration": session.get("current_iteration", 0)
            }
            for sid, session in active_sessions.items()
        ]
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    websocket_connections[session_id] = websocket

    try:
        # Send current session state
        if session_id in active_sessions:
            await websocket.send_json({
                "type": "session_state",
                "session": active_sessions[session_id]
            })

        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Echo back (can be used for heartbeat)
            await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        if session_id in websocket_connections:
            del websocket_connections[session_id]


@app.get("/api/download/{session_id}/{filename}")
async def download_file(session_id: str, filename: str):
    """Download a generated file from a session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_id]
    file_path = Path(session["output_directory"]) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its files."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = active_sessions[session_id]

    # Remove output directory
    output_dir = Path(session["output_directory"])
    if output_dir.exists():
        shutil.rmtree(output_dir)

    # Remove from active sessions
    del active_sessions[session_id]

    return {"status": "deleted", "message": "Session deleted successfully"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_sessions": len(active_sessions),
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn

    # Create necessary directories
    Path("templates").mkdir(exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    Path("static/css").mkdir(exist_ok=True)
    Path("static/js").mkdir(exist_ok=True)

    # Run the application
    uvicorn.run(
        "web_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
