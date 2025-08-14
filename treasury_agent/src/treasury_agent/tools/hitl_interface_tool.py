from crewai.tools import BaseTool
from typing import Type, Dict, Any, List, Optional
from pydantic import BaseModel, Field
import json
import datetime
import uuid
import time


class HitlInterfaceInput(BaseModel):
    """Input schema for HitlInterfaceTool."""
    proposal_data: str = Field(..., description="JSON string containing payment or investment proposal data")
    checkpoint_type: str = Field(..., description="Type of HITL checkpoint: 'payment_approval' or 'investment_approval'")
    user_id: str = Field(default="", description="User ID for approval tracking")
    timeout_minutes: int = Field(default=1440, description="Timeout in minutes for human response (default 24 hours)")


class HitlInterfaceTool(BaseTool):
    name: str = "Human-in-the-Loop Interface Manager"
    description: str = (
        "Manages human-in-the-loop checkpoints for payment and investment approvals. "
        "Formats proposals for human review, handles approval/rejection workflows, "
        "manages timeouts and escalations, stores decisions with audit trails, "
        "and interfaces with client-side UI for notifications and interactions."
    )
    args_schema: Type[BaseModel] = HitlInterfaceInput

    def _run(self, proposal_data: str, checkpoint_type: str, user_id: str = "", timeout_minutes: int = 1440) -> str:
        """
        Initiate and manage human-in-the-loop checkpoint for approval workflows.
        
        Args:
            proposal_data: JSON string with payment or investment proposal
            checkpoint_type: Type of checkpoint ('payment_approval' or 'investment_approval')
            user_id: User identifier for approval tracking
            timeout_minutes: Timeout period for human response
            
        Returns:
            JSON string containing HITL checkpoint status and formatted proposal for review
        """
        try:
            # Parse proposal data
            proposal = json.loads(proposal_data)
            
            # Generate unique checkpoint ID
            checkpoint_id = str(uuid.uuid4())
            
            # Initialize HITL checkpoint
            hitl_checkpoint = {
                "checkpoint_id": checkpoint_id,
                "checkpoint_type": checkpoint_type,
                "status": "PENDING_REVIEW",
                "created_at": datetime.datetime.now().isoformat(),
                "user_id": user_id,
                "timeout_deadline": (datetime.datetime.now() + datetime.timedelta(minutes=timeout_minutes)).isoformat(),
                "proposal_summary": {},
                "formatted_for_review": {},
                "approval_workflow": {
                    "required_approvals": 1,
                    "current_approvals": 0,
                    "approval_history": [],
                    "escalation_triggered": False
                },
                "notification_config": {
                    "immediate_notification": True,
                    "reminder_intervals": [60, 240, 720],  # minutes: 1hr, 4hr, 12hr
                    "escalation_threshold": timeout_minutes * 0.75
                },
                "audit_trail": [
                    {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "action": "CHECKPOINT_CREATED",
                        "details": f"HITL checkpoint created for {checkpoint_type}",
                        "user_id": "system"
                    }
                ]
            }
            
            # Format proposal based on checkpoint type
            if checkpoint_type == "payment_approval":
                self._format_payment_proposal(proposal, hitl_checkpoint)
            elif checkpoint_type == "investment_approval":
                self._format_investment_proposal(proposal, hitl_checkpoint)
            else:
                raise ValueError(f"Invalid checkpoint_type: {checkpoint_type}")
            
            # Determine approval requirements
            self._determine_approval_requirements(proposal, hitl_checkpoint)
            
            # Prepare notification payload
            self._prepare_notification_payload(hitl_checkpoint)
            
            return json.dumps(hitl_checkpoint, indent=2)
            
        except Exception as e:
            error_checkpoint = {
                "checkpoint_id": str(uuid.uuid4()),
                "checkpoint_type": checkpoint_type,
                "status": "ERROR",
                "error": str(e),
                "created_at": datetime.datetime.now().isoformat()
            }
            return json.dumps(error_checkpoint, indent=2)
    
    def _format_payment_proposal(self, proposal: Dict, checkpoint: Dict):
        """Format payment proposal for human review interface."""
        # Extract key information for summary
        summary = {
            "proposal_id": proposal.get("proposal_id"),
            "total_payments": proposal.get("summary", {}).get("total_payments", 0),
            "total_amount": proposal.get("summary", {}).get("total_amount", 0),
            "currency_breakdown": proposal.get("summary", {}).get("currency_breakdown", {}),
            "risk_level": proposal.get("summary", {}).get("risk_level", "UNKNOWN"),
            "flagged_payments": proposal.get("summary", {}).get("flagged_payments", 0),
            "requires_manual_review": proposal.get("approval_requirements", {}).get("requires_manual_review", False)
        }
        
        checkpoint["proposal_summary"] = summary
        
        # Format for human-readable review
        formatted_review = {
            "review_header": {
                "title": "Payment Proposal Approval Required",
                "urgency": self._determine_urgency(proposal),
                "reviewer_instructions": "Please review the payment details below and approve or reject the proposal."
            },
            "payment_overview": {
                "total_amount": f"${summary['total_amount']:,.2f}",
                "number_of_payments": summary["total_payments"],
                "risk_assessment": summary["risk_level"],
                "special_attention_required": summary["flagged_payments"] > 0
            },
            "payment_details": [],
            "risk_highlights": [],
            "approval_options": {
                "approve_all": {"label": "Approve All Payments", "requires_confirmation": True},
                "approve_selected": {"label": "Approve Selected Payments", "allows_modification": True},
                "reject_all": {"label": "Reject All Payments", "requires_reason": True},
                "request_modifications": {"label": "Request Modifications", "requires_reason": True}
            }
        }
        
        # Format individual payments for review
        for payment in proposal.get("individual_payments", []):
            payment_detail = {
                "payment_id": payment.get("payment_id"),
                "recipient": payment.get("recipient", {}).get("name", "Unknown"),
                "amount": f"${payment.get('amount', 0):,.2f}",
                "currency": payment.get("currency", "USD"),
                "description": payment.get("payment_details", {}).get("description", ""),
                "is_flagged": payment.get("validation", {}).get("is_flagged", False),
                "priority": payment.get("payment_details", {}).get("priority", "NORMAL"),
                "issues": payment.get("validation", {}).get("validation_errors", [])
            }
            formatted_review["payment_details"].append(payment_detail)
        
        # Add risk highlights
        risk_summary = proposal.get("risk_summary", {})
        if risk_summary.get("recommendations"):
            formatted_review["risk_highlights"] = risk_summary["recommendations"][:3]  # Top 3 recommendations
        
        checkpoint["formatted_for_review"] = formatted_review
    
    def _format_investment_proposal(self, proposal: Dict, checkpoint: Dict):
        """Format investment proposal for human review interface."""
        # Extract key information for summary
        summary = {
            "investment_plan_id": proposal.get("investment_plan_id"),
            "available_funds": proposal.get("available_funds", 0),
            "total_allocated": proposal.get("allocation_summary", {}).get("total_allocated", 0),
            "emergency_reserve": proposal.get("allocation_summary", {}).get("emergency_reserve", 0),
            "risk_level": proposal.get("risk_assessment", {}).get("overall_risk_level", "UNKNOWN"),
            "number_of_investments": len(proposal.get("recommended_investments", [])),
            "requires_high_approval": proposal.get("approval_requirements", {}).get("minimum_approval_level") == "HIGH"
        }
        
        checkpoint["proposal_summary"] = summary
        
        # Format for human-readable review
        formatted_review = {
            "review_header": {
                "title": "Investment Allocation Approval Required",
                "urgency": self._determine_urgency(proposal),
                "reviewer_instructions": "Please review the investment allocation strategy below and approve or modify as needed."
            },
            "investment_overview": {
                "total_investment_amount": f"${summary['total_allocated']:,.2f}",
                "emergency_reserve": f"${summary['emergency_reserve']:,.2f}",
                "risk_profile": summary["risk_level"],
                "diversification_strategy": "Multi-asset allocation"
            },
            "allocation_breakdown": {},
            "investment_recommendations": [],
            "risk_analysis": {},
            "approval_options": {
                "approve_as_proposed": {"label": "Approve as Proposed", "requires_confirmation": True},
                "modify_allocations": {"label": "Modify Allocations", "allows_editing": True},
                "reject_and_revise": {"label": "Reject and Request Revision", "requires_reason": True},
                "approve_partial": {"label": "Approve Selected Investments Only", "allows_selection": True}
            }
        }
        
        # Format allocation breakdown
        categories = proposal.get("allocation_summary", {}).get("investment_categories", {})
        for category, data in categories.items():
            formatted_review["allocation_breakdown"][category] = {
                "amount": f"${data.get('allocation', 0):,.2f}",
                "percentage": f"{data.get('percentage', 0)}%"
            }
        
        # Format investment recommendations
        for investment in proposal.get("recommended_investments", []):
            investment_detail = {
                "investment_id": investment.get("investment_id"),
                "type": investment.get("investment_type"),
                "category": investment.get("category"),
                "allocation": f"${investment.get('allocation', 0):,.2f}",
                "expected_return": investment.get("expected_return"),
                "risk_level": investment.get("risk_level"),
                "liquidity": investment.get("liquidity"),
                "description": investment.get("description", "")
            }
            formatted_review["investment_recommendations"].append(investment_detail)
        
        # Add risk analysis summary
        risk_assessment = proposal.get("risk_assessment", {})
        formatted_review["risk_analysis"] = {
            "diversification_score": f"{risk_assessment.get('diversification_score', 0)}%",
            "liquidity_ratio": f"{risk_assessment.get('liquidity_ratio', 0)}%",
            "overall_risk": risk_assessment.get("overall_risk_level", "UNKNOWN")
        }
        
        checkpoint["formatted_for_review"] = formatted_review
    
    def _determine_approval_requirements(self, proposal: Dict, checkpoint: Dict):
        """Determine specific approval requirements for the proposal."""
        approval_workflow = checkpoint["approval_workflow"]
        
        # Extract approval requirements from proposal
        approval_reqs = proposal.get("approval_requirements", {})
        
        # Set required approval count
        if checkpoint["checkpoint_type"] == "payment_approval":
            total_amount = proposal.get("summary", {}).get("total_amount", 0)
            risk_level = proposal.get("summary", {}).get("risk_level", "LOW")
            
            if risk_level in ["HIGH", "CRITICAL"] or total_amount > 100000:
                approval_workflow["required_approvals"] = 2
            elif total_amount > 50000:
                approval_workflow["required_approvals"] = 2
                
        elif checkpoint["checkpoint_type"] == "investment_approval":
            approval_level = approval_reqs.get("minimum_approval_level", "STANDARD")
            
            if approval_level == "HIGH":
                approval_workflow["required_approvals"] = 2
            elif approval_level == "MEDIUM":
                approval_workflow["required_approvals"] = 1
        
        # Set escalation requirements
        if approval_reqs.get("escalation_required", False):
            approval_workflow["required_approvals"] = max(approval_workflow["required_approvals"], 3)
            checkpoint["notification_config"]["escalation_threshold"] = checkpoint["notification_config"]["escalation_threshold"] * 0.5
    
    def _determine_urgency(self, proposal: Dict) -> str:
        """Determine urgency level for the proposal."""
        if proposal.get("approval_requirements", {}).get("escalation_required", False):
            return "CRITICAL"
        elif proposal.get("summary", {}).get("risk_level") in ["HIGH", "CRITICAL"]:
            return "HIGH"
        elif proposal.get("approval_requirements", {}).get("requires_manual_review", False):
            return "MEDIUM"
        else:
            return "NORMAL"
    
    def _prepare_notification_payload(self, checkpoint: Dict):
        """Prepare notification payload for client-side UI."""
        checkpoint_type = checkpoint["checkpoint_type"]
        summary = checkpoint["proposal_summary"]
        
        notification_payload = {
            "notification_id": str(uuid.uuid4()),
            "checkpoint_id": checkpoint["checkpoint_id"],
            "type": f"{checkpoint_type}_required",
            "urgency": checkpoint["formatted_for_review"]["review_header"]["urgency"],
            "title": checkpoint["formatted_for_review"]["review_header"]["title"],
            "message": self._generate_notification_message(checkpoint_type, summary),
            "action_required": True,
            "deep_link": f"/agent/review/{checkpoint['checkpoint_id']}",
            "expires_at": checkpoint["timeout_deadline"],
            "metadata": {
                "proposal_id": summary.get("proposal_id") or summary.get("investment_plan_id"),
                "amount": summary.get("total_amount") or summary.get("total_allocated"),
                "requires_immediate_attention": summary.get("requires_manual_review") or summary.get("requires_high_approval")
            }
        }
        
        checkpoint["notification_payload"] = notification_payload
    
    def _generate_notification_message(self, checkpoint_type: str, summary: Dict) -> str:
        """Generate human-readable notification message."""
        if checkpoint_type == "payment_approval":
            amount = summary.get("total_amount", 0)
            count = summary.get("total_payments", 0)
            return f"Payment approval required: {count} payments totaling ${amount:,.2f}"
        elif checkpoint_type == "investment_approval":
            amount = summary.get("total_allocated", 0)
            count = summary.get("number_of_investments", 0)
            return f"Investment approval required: {count} investment allocations totaling ${amount:,.2f}"
        else:
            return "Approval required for treasury operation"
