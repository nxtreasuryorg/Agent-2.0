from crewai.tools import BaseTool
from typing import Type, Dict, Any, List
from pydantic import BaseModel, Field
import json
import datetime
import uuid
from decimal import Decimal, ROUND_HALF_UP


class PaymentFormatterInput(BaseModel):
    """Input schema for PaymentFormatterTool."""
    financial_data: str = Field(..., description="JSON string containing normalized financial data from Excel parsing")
    risk_report: str = Field(..., description="JSON string containing risk assessment report")
    user_constraints: Dict[str, Any] = Field(
        default={}, 
        description="User-defined constraints and payment preferences"
    )


class PaymentFormatterTool(BaseTool):
    name: str = "Payment Proposal Formatter"
    description: str = (
        "Generates structured payment proposals from financial data and risk assessments. "
        "Creates human-readable payment summaries, batch processing recommendations, "
        "compliance checks, and formats proposals for HITL approval workflow."
    )
    args_schema: Type[BaseModel] = PaymentFormatterInput

    def _run(self, financial_data: str, risk_report: str, user_constraints: Dict[str, Any] = None) -> str:
        """
        Generate structured payment proposal from financial data and risk assessment.
        
        Args:
            financial_data: JSON string with normalized financial data
            risk_report: JSON string with risk assessment results
            user_constraints: User-defined payment preferences and constraints
            
        Returns:
            JSON string containing formatted payment proposal for HITL review
        """
        try:
            if user_constraints is None:
                user_constraints = {}
                
            # Parse input data
            financial_data_obj = json.loads(financial_data)
            risk_data = json.loads(risk_report)
            normalized_records = financial_data_obj.get("normalized_data", [])
            
            # Generate unique proposal ID
            proposal_id = str(uuid.uuid4())
            
            # Initialize payment proposal
            payment_proposal = {
                "proposal_id": proposal_id,
                "timestamp": datetime.datetime.now().isoformat(),
                "status": "PENDING_APPROVAL",
                "summary": {
                    "total_payments": len(normalized_records),
                    "total_amount": 0.0,
                    "currency_breakdown": {},
                    "risk_level": risk_data.get("risk_assessment", {}).get("risk_level", "MEDIUM"),
                    "compliance_status": risk_data.get("risk_assessment", {}).get("compliance_status", "PENDING")
                },
                "payment_batches": [],
                "individual_payments": [],
                "risk_summary": {
                    "flagged_transactions": len(risk_data.get("flagged_transactions", [])),
                    "constraint_violations": len(risk_data.get("risk_factors", {}).get("constraint_violations", [])),
                    "recommendations": risk_data.get("recommendations", [])
                },
                "approval_requirements": {
                    "requires_manual_review": False,
                    "required_approvers": 1,
                    "approval_deadline": None,
                    "escalation_required": False
                },
                "metadata": {
                    "user_constraints": user_constraints,
                    "processing_options": {
                        "batch_processing": True,
                        "immediate_execution": False,
                        "schedule_for_later": False
                    }
                }
            }
            
            if not normalized_records:
                payment_proposal["status"] = "NO_PAYMENTS_REQUIRED"
                payment_proposal["summary"]["message"] = "No valid payment transactions found"
                return json.dumps(payment_proposal, indent=2)
            
            # Process and format payments
            self._process_payments(normalized_records, payment_proposal, risk_data)
            self._create_payment_batches(payment_proposal, user_constraints)
            self._determine_approval_requirements(payment_proposal, risk_data, user_constraints)
            self._calculate_summary_statistics(payment_proposal)
            
            return json.dumps(payment_proposal, indent=2)
            
        except Exception as e:
            error_proposal = {
                "proposal_id": str(uuid.uuid4()),
                "timestamp": datetime.datetime.now().isoformat(),
                "status": "ERROR",
                "error": str(e),
                "summary": {
                    "total_payments": 0,
                    "total_amount": 0.0
                }
            }
            return json.dumps(error_proposal, indent=2)
    
    def _process_payments(self, records: List[Dict], proposal: Dict, risk_data: Dict):
        """Process individual payments and format for proposal."""
        flagged_transaction_ids = set()
        for flagged in risk_data.get("flagged_transactions", []):
            flagged_transaction_ids.add(flagged.get("transaction_id", ""))
        
        individual_payments = []
        
        for record in records:
            transaction_id = f"{record.get('sheet_name', '')}_row_{record.get('row_number', '')}"
            amount = float(record.get("amount", 0))
            
            # Format individual payment
            payment = {
                "payment_id": str(uuid.uuid4()),
                "transaction_id": transaction_id,
                "amount": self._format_currency(amount),
                "currency": record.get("currency", "USD"),
                "recipient": {
                    "name": record.get("recipient", "Unknown Recipient"),
                    "account": record.get("account", ""),
                    "reference": record.get("description", "Payment")
                },
                "payment_details": {
                    "description": record.get("description", ""),
                    "category": record.get("category", "General Payment"),
                    "date_requested": record.get("date"),
                    "priority": "NORMAL"
                },
                "validation": {
                    "is_flagged": transaction_id in flagged_transaction_ids,
                    "validation_errors": record.get("validation_errors", []),
                    "compliance_issues": record.get("compliance_issues", [])
                },
                "raw_data": record.get("raw_data", {})
            }
            
            # Set priority based on amount and flags
            if amount > 50000:
                payment["payment_details"]["priority"] = "HIGH"
            elif payment["validation"]["is_flagged"]:
                payment["payment_details"]["priority"] = "REVIEW_REQUIRED"
            
            individual_payments.append(payment)
        
        proposal["individual_payments"] = individual_payments
    
    def _create_payment_batches(self, proposal: Dict, user_constraints: Dict):
        """Create logical payment batches for processing efficiency."""
        payments = proposal["individual_payments"]
        
        # Group payments by currency and priority
        batches = {}
        
        for payment in payments:
            currency = payment["currency"]
            priority = payment["payment_details"]["priority"]
            batch_key = f"{currency}_{priority}"
            
            if batch_key not in batches:
                batches[batch_key] = {
                    "batch_id": str(uuid.uuid4()),
                    "currency": currency,
                    "priority": priority,
                    "payments": [],
                    "total_amount": 0.0,
                    "payment_count": 0,
                    "requires_review": False,
                    "estimated_processing_time": "1-2 business days"
                }
            
            batches[batch_key]["payments"].append(payment["payment_id"])
            batches[batch_key]["total_amount"] += payment["amount"]
            batches[batch_key]["payment_count"] += 1
            
            if payment["validation"]["is_flagged"] or payment["payment_details"]["priority"] == "REVIEW_REQUIRED":
                batches[batch_key]["requires_review"] = True
                batches[batch_key]["estimated_processing_time"] = "3-5 business days"
        
        # Sort batches by priority
        priority_order = {"HIGH": 0, "REVIEW_REQUIRED": 1, "NORMAL": 2}
        sorted_batches = sorted(
            batches.values(), 
            key=lambda x: (priority_order.get(x["priority"], 3), -x["total_amount"])
        )
        
        proposal["payment_batches"] = sorted_batches
    
    def _determine_approval_requirements(self, proposal: Dict, risk_data: Dict, user_constraints: Dict):
        """Determine approval requirements based on risk and constraints."""
        approval_reqs = proposal["approval_requirements"]
        
        risk_level = risk_data.get("risk_assessment", {}).get("risk_level", "MEDIUM")
        total_amount = sum(payment["amount"] for payment in proposal["individual_payments"])
        flagged_count = len(risk_data.get("flagged_transactions", []))
        violation_count = len(risk_data.get("risk_factors", {}).get("constraint_violations", []))
        
        # Determine if manual review is required
        if risk_level in ["HIGH", "CRITICAL"]:
            approval_reqs["requires_manual_review"] = True
            approval_reqs["required_approvers"] = 2
        elif total_amount > user_constraints.get("auto_approval_limit", 100000):
            approval_reqs["requires_manual_review"] = True
        elif flagged_count > 0 or violation_count > 0:
            approval_reqs["requires_manual_review"] = True
        
        # Set approval deadline
        if approval_reqs["requires_manual_review"]:
            deadline = datetime.datetime.now() + datetime.timedelta(hours=24)
            approval_reqs["approval_deadline"] = deadline.isoformat()
        
        # Determine escalation requirements
        if risk_level == "CRITICAL" or total_amount > user_constraints.get("escalation_threshold", 500000):
            approval_reqs["escalation_required"] = True
            approval_reqs["required_approvers"] = 3
        
        # Set processing options based on approval requirements
        if approval_reqs["requires_manual_review"]:
            proposal["metadata"]["processing_options"]["immediate_execution"] = False
            proposal["metadata"]["processing_options"]["batch_processing"] = True
    
    def _calculate_summary_statistics(self, proposal: Dict):
        """Calculate summary statistics for the payment proposal."""
        payments = proposal["individual_payments"]
        summary = proposal["summary"]
        
        if not payments:
            return
        
        # Calculate totals
        total_amount = sum(payment["amount"] for payment in payments)
        summary["total_amount"] = self._format_currency(total_amount)
        summary["total_payments"] = len(payments)
        
        # Currency breakdown
        currency_breakdown = {}
        for payment in payments:
            currency = payment["currency"]
            if currency not in currency_breakdown:
                currency_breakdown[currency] = {
                    "amount": 0.0,
                    "count": 0
                }
            currency_breakdown[currency]["amount"] += payment["amount"]
            currency_breakdown[currency]["count"] += 1
        
        # Format currency amounts
        for currency, data in currency_breakdown.items():
            data["amount"] = self._format_currency(data["amount"])
        
        summary["currency_breakdown"] = currency_breakdown
        
        # Payment priority breakdown
        priority_breakdown = {}
        for payment in payments:
            priority = payment["payment_details"]["priority"]
            if priority not in priority_breakdown:
                priority_breakdown[priority] = 0
            priority_breakdown[priority] += 1
        
        summary["priority_breakdown"] = priority_breakdown
        
        # Risk and compliance summary
        flagged_payments = [p for p in payments if p["validation"]["is_flagged"]]
        summary["flagged_payments"] = len(flagged_payments)
        
        payments_with_issues = [p for p in payments if p["validation"]["compliance_issues"]]
        summary["compliance_issues"] = len(payments_with_issues)
        
        # Batch summary
        batches = proposal["payment_batches"]
        summary["total_batches"] = len(batches)
        summary["batches_requiring_review"] = len([b for b in batches if b["requires_review"]])
    
    def _format_currency(self, amount: float) -> float:
        """Format currency amount to 2 decimal places."""
        return float(Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
