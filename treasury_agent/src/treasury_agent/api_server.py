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

from .crew import TreasuryAgent

# Initialize FastAPI app
app = FastAPI(
    title="Treasury Manager AI Agent API",
    description="API for managing treasury workflows with AI agents",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
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
    type: str
    timestamp: str
    status: str
    payment_details: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    constraints_validation: Dict[str, Any]
    summary: Dict[str, Any]
    approval_metadata: Dict[str, Any]

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
        
        # Process workflow (async) - Convert API schema to internal format
        constraints = {
            "minimum_balance": request_config.risk_config.min_balance_usd,
            "transaction_limits": request_config.risk_config.transaction_limits,
            "custody_wallet": request_config.custody_wallet,
            "private_key": request_config.private_key,
            "user_id": request_config.user_id,
            "user_notes": request_config.user_notes
        }
        
        workflow_result = await crew.process_workflow(
            excel_data=excel_content,
            constraints=constraints,
            risk_tolerance="medium"  # Default for now
        )
        
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
    
    # Ensure proposal has required fields
    if "proposal_id" not in proposal:
        proposal["proposal_id"] = proposal_id
    
    return PaymentProposal(**proposal)

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
