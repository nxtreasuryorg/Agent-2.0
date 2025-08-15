"""Proposal Formatter Tool for creating structured payment proposals."""
from typing import Dict, Any, List
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from datetime import datetime
import json

class ProposalFormatterInput(BaseModel):
    """Input schema for Proposal Formatter Tool."""
    payment_data: Dict[str, Any] = Field(description="Payment data to format")
    risk_assessment: Dict[str, Any] = Field(description="Risk assessment results")
    constraints: Dict[str, Any] = Field(description="User-defined constraints")

class ProposalFormatterTool(BaseTool):
    name: str = "Proposal Formatter Tool"
    description: str = """
    Format payment proposals in a structured, human-readable format.
    Creates standardized proposals with all necessary information for HITL review.
    """
    args_schema: type[BaseModel] = ProposalFormatterInput

    def _run(self, payment_data: Dict[str, Any], risk_assessment: Dict[str, Any], 
             constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Format payment proposal for human review."""
        try:
            # Generate unique proposal ID
            proposal_id = f"PAY-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            # Structure the payment proposal
            proposal = {
                "proposal_id": proposal_id,
                "type": "payment_proposal",
                "timestamp": datetime.now().isoformat(),
                "status": "pending_approval",
                
                "payment_details": {
                    "total_amount": payment_data.get("total_amount", 0),
                    "currency": payment_data.get("currency", "USD"),
                    "payment_count": len(payment_data.get("payments", [])),
                    "payments": []
                },
                
                "risk_assessment": {
                    "risk_level": risk_assessment.get("risk_level", "medium"),
                    "risk_score": risk_assessment.get("risk_score", 0),
                    "flags": risk_assessment.get("flags", []),
                    "compliance_status": risk_assessment.get("compliance_status", "pending")
                },
                
                "constraints_validation": {
                    "minimum_balance": {
                        "required": constraints.get("minimum_balance", 0),
                        "after_payment": payment_data.get("remaining_balance", 0),
                        "satisfied": payment_data.get("remaining_balance", 0) >= constraints.get("minimum_balance", 0)
                    },
                    "transaction_limits": {
                        "max_per_transaction": constraints.get("max_transaction", float('inf')),
                        "max_total": constraints.get("max_total", float('inf')),
                        "satisfied": True
                    }
                },
                
                "summary": {
                    "total_payments": len(payment_data.get("payments", [])),
                    "total_amount": payment_data.get("total_amount", 0),
                    "estimated_processing_time": "2-3 business days",
                    "approval_required": True
                }
            }
            
            # Format individual payments
            for payment in payment_data.get("payments", []):
                formatted_payment = {
                    "recipient": payment.get("recipient", "Unknown"),
                    "amount": payment.get("amount", 0),
                    "reference": payment.get("reference", ""),
                    "due_date": payment.get("due_date", ""),
                    "priority": payment.get("priority", "normal"),
                    "category": payment.get("category", "general")
                }
                proposal["payment_details"]["payments"].append(formatted_payment)
            
            # Check transaction limits
            for payment in proposal["payment_details"]["payments"]:
                if payment["amount"] > constraints.get("max_transaction", float('inf')):
                    proposal["constraints_validation"]["transaction_limits"]["satisfied"] = False
                    break
            
            if proposal["payment_details"]["total_amount"] > constraints.get("max_total", float('inf')):
                proposal["constraints_validation"]["transaction_limits"]["satisfied"] = False
            
            # Add approval metadata
            proposal["approval_metadata"] = {
                "requires_approval": True,
                "approval_level": "standard" if proposal["risk_assessment"]["risk_level"] == "low" else "enhanced",
                "expires_at": datetime.now().isoformat(),
                "approval_actions": ["approve", "reject", "modify"]
            }
            
            return proposal
            
        except Exception as e:
            return {
                "error": str(e),
                "success": False,
                "metadata": {"error_type": type(e).__name__}
            }
