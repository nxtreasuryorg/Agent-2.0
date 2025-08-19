"""FastAPI server for Treasury Manager AI Agent API endpoints"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import json
import asyncio
from datetime import datetime
import uuid
import os
import logging

from .crew import TreasuryAgent

# Initialize FastAPI app
app = FastAPI(
    title="Treasury Manager AI Agent API",
    description="API for managing treasury workflows with AI agents",
    version="1.0.0"
)

# Configure logging level for this module so INFO shows up under uvicorn
logging.basicConfig(level=logging.INFO)

# Configure CORS
allowed_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5000,http://127.0.0.1:3000,http://127.0.0.1:5000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Configurable origins from environment
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Specific methods only
    allow_headers=["*"],
)

# In-memory storage for workflow states and proposals
# In production, use a proper database
workflow_storage: Dict[str, Any] = {}
proposal_storage: Dict[str, Any] = {}
crew_instances: Dict[str, TreasuryAgent] = {}

# Pydantic models for request/response
class HealthResponse(BaseModel):
    status: str

class ErrorResponse(BaseModel):
    error: str
    success: bool = False

class RiskConfig(BaseModel):
    min_balance_usd: float = Field(description="Minimum balance required in USD")
    transaction_limits: Dict[str, float] = Field(description="Single and daily transaction limits")

class RequestConfig(BaseModel):
    user_id: str = Field(description="User identifier")
    custody_wallet: str = Field(description="Custody wallet address")
    private_key: str = Field(description="Private key for transactions")
    risk_config: RiskConfig = Field(description="Risk configuration parameters")
    user_notes: str = Field(default="", description="Additional user notes")

class SubmitRequestResponse(BaseModel):
    success: bool
    proposal_id: str
    message: str
    next_step: str

class PaymentProposal(BaseModel):
    proposal_id: str
    agent_analysis: Optional[Dict[str, Any]] = None  # Required by API docs
    payment_proposals: Optional[List[Dict[str, Any]]] = None  # Required by API docs  
    risk_assessment: Dict[str, Any]
    
    # Legacy fields for backward compatibility
    type: Optional[str] = None
    timestamp: Optional[str] = None
    status: Optional[str] = None
    payment_details: Optional[Dict[str, Any]] = None
    constraints_validation: Optional[Dict[str, Any]] = None
    summary: Optional[Dict[str, Any]] = None
    approval_metadata: Optional[Dict[str, Any]] = None

class PaymentApprovalRequest(BaseModel):
    proposal_id: str
    approval_decision: str = Field(description="approve_all | reject_all | partial")
    approved_payments: Optional[List[str]] = Field(default=None, description="List of payment IDs for partial approval")
    comments: Optional[str] = None

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy")

@app.post("/submit_request", response_model=SubmitRequestResponse)
async def submit_request(
    excel_file: UploadFile = File(...),
    config: str = Form(...)
):
    """Submit a new treasury workflow request with Excel file and configuration"""
    try:
        # Parse configuration JSON
        try:
            config_data = json.loads(config)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON configuration: {str(e)}")
        
        # Validate configuration against documented schema
        try:
            request_config = RequestConfig(**config_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid configuration schema: {str(e)}")
        
        # Read Excel file content
        excel_content = await excel_file.read()
        
        # Generate unique proposal ID
        proposal_id = f"PROP-{uuid.uuid4().hex[:12]}"
        
        # Create new crew instance
        crew = TreasuryAgent()
        crew_instances[proposal_id] = crew
        logging.info(f"[submit_request] Received request. proposal_id={proposal_id}, filename={excel_file.filename}")

        # Process workflow (async) - Convert API schema to internal format
        constraints = {
            "minimum_balance": request_config.risk_config.min_balance_usd,
            "transaction_limits": request_config.risk_config.transaction_limits,
            "custody_wallet": request_config.custody_wallet,
            "private_key": request_config.private_key,
            "user_id": request_config.user_id,
            "user_notes": request_config.user_notes
        }
        
        # CrewAI kickoff behavior: default to ON and BLOCKING per requirements
        use_crew = os.environ.get("TREASURY_USE_CREW", "true").lower() == "true"
        crew_blocking = os.environ.get("TREASURY_CREW_BLOCKING", "true").lower() == "true"
        if use_crew:
            try:
                crew_inputs = {
                    # Make constraints available to task templates (e.g., tasks.yaml placeholders)
                    "minimum_balance": constraints.get("minimum_balance"),
                    "transaction_limits": constraints.get("transaction_limits"),
                    "user_notes": constraints.get("user_notes"),
                    "user_id": constraints.get("user_id"),
                    "current_year": str(datetime.now().year),
                }
                if crew_blocking:
                    logging.info(f"[submit_request] Starting CrewAI kickoff (blocking). proposal_id={proposal_id}")
                    # Run kickoff in a worker thread and await completion so FastAPI loop isn't blocked
                    kick_result = await asyncio.to_thread(lambda: crew.crew().kickoff(inputs=crew_inputs))
                    logging.info(f"[submit_request] CrewAI kickoff finished (blocking). proposal_id={proposal_id}")
                else:
                    logging.info(f"[submit_request] Starting CrewAI kickoff (non-blocking). proposal_id={proposal_id}")
                    asyncio.create_task(asyncio.to_thread(lambda: crew.crew().kickoff(inputs=crew_inputs)))
            except Exception as e:
                logging.warning(f"[submit_request] CrewAI kickoff failed (continuing with tool flow). error={e}")

        logging.info(f"[submit_request] Starting tool-based workflow processing. proposal_id={proposal_id}")
        workflow_result = await crew.process_workflow(
            excel_data=excel_content,
            constraints=constraints,
            risk_tolerance="medium"  # Default for now
        )
        logging.info(f"[submit_request] Workflow processing finished. proposal_id={proposal_id}, status={workflow_result.get('status')}")

        # Store workflow state
        workflow_storage[proposal_id] = workflow_result
        
        # Extract and store payment proposal
        if "payment_proposal" in workflow_result:
            proposal_storage[proposal_id] = workflow_result["payment_proposal"]
        
        return SubmitRequestResponse(
            success=True,
            proposal_id=proposal_id,
            message="Proposal generated successfully.",
            next_step=f"GET /get_payment_proposal/{proposal_id}"
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "success": False}
        )

@app.get("/get_payment_proposal/{proposal_id}", response_model=PaymentProposal)
async def get_payment_proposal(proposal_id: str):
    """Retrieve payment proposal by ID"""
    if proposal_id not in proposal_storage:
        raise HTTPException(status_code=404, detail="Payment proposal not found")
    
    proposal = proposal_storage[proposal_id]
    
    # Ensure proposal has required fields and matches API documentation format
    if "proposal_id" not in proposal:
        proposal["proposal_id"] = proposal_id
    
    # Transform proposal to match API documentation format
    api_format_proposal = {
        "proposal_id": proposal_id,
        "agent_analysis": proposal.get("analysis", {}),
        "payment_proposals": proposal.get("payment_details", {}).get("payments", []),
        "risk_assessment": proposal.get("risk_assessment", {}),
        # Keep legacy fields for backward compatibility
        **proposal
    }
    
    return PaymentProposal(**api_format_proposal)

@app.post("/submit_payment_approval")
async def submit_payment_approval(approval: PaymentApprovalRequest):
    """Submit approval/rejection for payment proposal"""
    try:
        proposal_id = approval.proposal_id
        
        if proposal_id not in workflow_storage:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        if proposal_id not in crew_instances:
            raise HTTPException(status_code=404, detail="Crew instance not found")
        
        crew = crew_instances[proposal_id]
        
        # Continue workflow after payment approval  
        approval_status = "approved" if approval.approval_decision == "approve_all" else "rejected"
        updated_workflow = await crew.continue_after_payment_approval(
            proposal_id=proposal_id,
            approval_status=approval_status
        )
        
        # Update storage
        workflow_storage[proposal_id] = updated_workflow
        
        execution_status = updated_workflow.get("payment_execution", {}).get("status", "SUCCESS")
        return {
            "success": True,
            "execution_status": execution_status,
            "message": "Execution summary.",
            "next_step": f"GET /payment_execution_result/{proposal_id}"
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "success": False}
        )

@app.get("/payment_execution_result/{proposal_id}")
async def get_payment_execution_result(proposal_id: str):
    """Get payment execution results"""
    if proposal_id not in workflow_storage:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    workflow = workflow_storage[proposal_id]
    
    if "payment_execution" not in workflow:
        raise HTTPException(status_code=404, detail="Payment execution not found")
    
    return workflow["payment_execution"]


# Additional endpoints for workflow management
@app.get("/workflow_status/{proposal_id}")
async def get_workflow_status(proposal_id: str):
    """Get the current status of a workflow"""
    if proposal_id not in workflow_storage:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    workflow = workflow_storage[proposal_id]
    return {
        "proposal_id": proposal_id,
        "status": workflow.get("status"),
        "steps_completed": workflow.get("steps_completed", []),
        "requires_approval": workflow.get("requires_approval"),
        "start_time": workflow.get("start_time"),
        "end_time": workflow.get("end_time")
    }

@app.get("/list_workflows")
async def list_workflows():
    """List all workflows with their statuses"""
    workflows = []
    for proposal_id, workflow in workflow_storage.items():
        workflows.append({
            "proposal_id": proposal_id,
            "status": workflow.get("status"),
            "start_time": workflow.get("start_time"),
            "end_time": workflow.get("end_time"),
            "steps_completed": len(workflow.get("steps_completed", []))
        })
    return {"workflows": workflows, "total": len(workflows)}

# Run the server
if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or use default
    port = int(os.environ.get("PORT", 5001))
    
    # Run server
    uvicorn.run(
        "treasury_agent.api_server:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
