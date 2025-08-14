from crewai.tools import BaseTool
from typing import Type, Dict, Any, List
from pydantic import BaseModel, Field
import json
import datetime
from decimal import Decimal


class RiskAssessmentInput(BaseModel):
    """Input schema for RiskAssessmentTool."""
    financial_data: str = Field(..., description="JSON string containing normalized financial data from Excel parsing")
    user_constraints: Dict[str, Any] = Field(
        default={}, 
        description="User-defined constraints including minimum balance, transaction limits, special conditions"
    )


class RiskAssessmentTool(BaseTool):
    name: str = "Financial Risk Assessment Analyzer"
    description: str = (
        "Evaluates financial data against user-defined constraints, performs comprehensive risk analysis "
        "considering regulatory compliance, transaction patterns, and generates detailed risk reports with "
        "risk scores, compliance status, and recommendations."
    )
    args_schema: Type[BaseModel] = RiskAssessmentInput

    def _run(self, financial_data: str, user_constraints: Dict[str, Any] = None) -> str:
        """
        Perform comprehensive risk assessment on financial data.
        
        Args:
            financial_data: JSON string with normalized financial data
            user_constraints: User-defined financial constraints and limits
            
        Returns:
            JSON string containing detailed risk assessment report
        """
        try:
            if user_constraints is None:
                user_constraints = {}
                
            # Parse input data
            data = json.loads(financial_data)
            normalized_records = data.get("normalized_data", [])
            
            # Initialize risk assessment result
            risk_report = {
                "success": True,
                "timestamp": datetime.datetime.now().isoformat(),
                "risk_assessment": {
                    "overall_risk_score": 0.0,  # 0-10 scale (10 = highest risk)
                    "risk_level": "LOW",  # LOW, MEDIUM, HIGH, CRITICAL
                    "compliance_status": "COMPLIANT",
                    "total_amount": 0.0,
                    "transaction_count": len(normalized_records)
                },
                "risk_factors": {
                    "amount_risks": [],
                    "pattern_risks": [],
                    "compliance_risks": [],
                    "constraint_violations": []
                },
                "flagged_transactions": [],
                "recommendations": [],
                "detailed_analysis": {}
            }
            
            if not normalized_records:
                risk_report["risk_assessment"]["risk_level"] = "LOW"
                risk_report["recommendations"].append("No financial transactions to assess")
                return json.dumps(risk_report, indent=2)
            
            # Perform comprehensive risk analysis
            self._analyze_amount_risks(normalized_records, user_constraints, risk_report)
            self._analyze_transaction_patterns(normalized_records, risk_report)
            self._analyze_compliance_risks(normalized_records, risk_report)
            self._analyze_user_constraints(normalized_records, user_constraints, risk_report)
            
            # Calculate overall risk score and level
            self._calculate_overall_risk(risk_report)
            
            # Generate recommendations
            self._generate_recommendations(risk_report, user_constraints)
            
            return json.dumps(risk_report, indent=2)
            
        except Exception as e:
            error_report = {
                "success": False,
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat(),
                "risk_assessment": {
                    "risk_level": "CRITICAL",
                    "compliance_status": "ERROR"
                }
            }
            return json.dumps(error_report, indent=2)
    
    def _analyze_amount_risks(self, records: List[Dict], user_constraints: Dict, risk_report: Dict):
        """Analyze risks related to transaction amounts."""
        amounts = [float(record.get("amount", 0)) for record in records if record.get("amount")]
        
        if not amounts:
            return
            
        total_amount = sum(amounts)
        max_amount = max(amounts)
        avg_amount = total_amount / len(amounts)
        
        risk_report["risk_assessment"]["total_amount"] = total_amount
        risk_report["detailed_analysis"]["amount_analysis"] = {
            "total_amount": total_amount,
            "max_transaction": max_amount,
            "average_transaction": avg_amount,
            "transaction_count": len(amounts)
        }
        
        # High-value transaction risk
        high_value_threshold = user_constraints.get("high_value_threshold", 100000)
        high_value_transactions = [amt for amt in amounts if amt > high_value_threshold]
        
        if high_value_transactions:
            risk_factor = {
                "type": "HIGH_VALUE_TRANSACTIONS",
                "severity": "MEDIUM",
                "count": len(high_value_transactions),
                "description": f"{len(high_value_transactions)} transactions exceed high-value threshold of ${high_value_threshold:,.2f}",
                "risk_score": min(3.0, len(high_value_transactions) * 0.5)
            }
            risk_report["risk_factors"]["amount_risks"].append(risk_factor)
        
        # Large aggregate amount risk
        if total_amount > user_constraints.get("daily_limit", 1000000):
            risk_factor = {
                "type": "AGGREGATE_AMOUNT_RISK",
                "severity": "HIGH",
                "description": f"Total transaction amount ${total_amount:,.2f} exceeds daily limit",
                "risk_score": 4.0
            }
            risk_report["risk_factors"]["amount_risks"].append(risk_factor)
        
        # Flag individual high-risk transactions
        for record in records:
            amount = float(record.get("amount", 0))
            if amount > high_value_threshold:
                risk_report["flagged_transactions"].append({
                    "transaction_id": f"{record.get('sheet_name', '')}_row_{record.get('row_number', '')}",
                    "amount": amount,
                    "reason": "High-value transaction requiring additional review",
                    "recipient": record.get("recipient", "Unknown"),
                    "description": record.get("description", "")
                })
    
    def _analyze_transaction_patterns(self, records: List[Dict], risk_report: Dict):
        """Analyze transaction patterns for anomalies."""
        pattern_risks = []
        
        # Duplicate recipient analysis
        recipients = {}
        for record in records:
            recipient = record.get("recipient", "Unknown").strip().lower()
            if recipient and recipient != "unknown":
                recipients[recipient] = recipients.get(recipient, 0) + 1
        
        # Flag multiple payments to same recipient
        high_frequency_recipients = {k: v for k, v in recipients.items() if v > 3}
        if high_frequency_recipients:
            risk_factor = {
                "type": "DUPLICATE_RECIPIENTS",
                "severity": "LOW",
                "description": f"Multiple transactions to same recipients: {len(high_frequency_recipients)} recipients",
                "details": high_frequency_recipients,
                "risk_score": 1.0
            }
            pattern_risks.append(risk_factor)
        
        # Round number analysis (potential fraud indicator)
        amounts = [float(record.get("amount", 0)) for record in records if record.get("amount")]
        round_numbers = [amt for amt in amounts if amt % 100 == 0 and amt > 1000]
        
        if len(round_numbers) > len(amounts) * 0.5:  # More than 50% round numbers
            risk_factor = {
                "type": "ROUND_NUMBER_PATTERN",
                "severity": "LOW",
                "description": f"High percentage of round-number transactions: {len(round_numbers)}/{len(amounts)}",
                "risk_score": 1.5
            }
            pattern_risks.append(risk_factor)
        
        risk_report["risk_factors"]["pattern_risks"] = pattern_risks
        risk_report["detailed_analysis"]["pattern_analysis"] = {
            "unique_recipients": len(recipients),
            "high_frequency_recipients": len(high_frequency_recipients),
            "round_number_percentage": (len(round_numbers) / len(amounts) * 100) if amounts else 0
        }
    
    def _analyze_compliance_risks(self, records: List[Dict], risk_report: Dict):
        """Analyze regulatory and compliance risks."""
        compliance_risks = []
        
        # Missing required information
        missing_info_count = 0
        for record in records:
            missing_fields = []
            if not record.get("recipient") or record.get("recipient") == "Unknown":
                missing_fields.append("recipient")
            if not record.get("description") or record.get("description") in ["", "No description provided"]:
                missing_fields.append("description")
            if not record.get("date"):
                missing_fields.append("date")
            
            if missing_fields:
                missing_info_count += 1
                record["compliance_issues"] = missing_fields
        
        if missing_info_count > 0:
            severity = "HIGH" if missing_info_count > len(records) * 0.3 else "MEDIUM"
            risk_factor = {
                "type": "MISSING_REQUIRED_INFO",
                "severity": severity,
                "description": f"{missing_info_count} transactions missing required information",
                "risk_score": 2.0 if severity == "MEDIUM" else 3.5
            }
            compliance_risks.append(risk_factor)
        
        # Currency compliance (for international transactions)
        currencies = set(record.get("currency", "USD") for record in records)
        if len(currencies) > 1:
            risk_factor = {
                "type": "MULTI_CURRENCY",
                "severity": "MEDIUM",
                "description": f"Multiple currencies detected: {list(currencies)}",
                "risk_score": 2.0
            }
            compliance_risks.append(risk_factor)
        
        risk_report["risk_factors"]["compliance_risks"] = compliance_risks
        risk_report["detailed_analysis"]["compliance_analysis"] = {
            "transactions_with_missing_info": missing_info_count,
            "currencies_used": list(currencies),
            "data_completeness_score": (len(records) - missing_info_count) / len(records) * 100 if records else 100
        }
    
    def _analyze_user_constraints(self, records: List[Dict], user_constraints: Dict, risk_report: Dict):
        """Analyze violations of user-defined constraints."""
        constraint_violations = []
        
        min_balance = user_constraints.get("minimum_balance", 0)
        transaction_limit = user_constraints.get("transaction_limit")
        daily_limit = user_constraints.get("daily_limit")
        
        # Check individual transaction limits
        violation_count = 0
        for record in records:
            amount = float(record.get("amount", 0))
            
            if amount < min_balance:
                violation_count += 1
                constraint_violations.append({
                    "type": "BELOW_MINIMUM_BALANCE",
                    "transaction_id": f"{record.get('sheet_name', '')}_row_{record.get('row_number', '')}",
                    "amount": amount,
                    "limit": min_balance,
                    "description": f"Transaction ${amount:,.2f} below minimum balance requirement"
                })
            
            if transaction_limit and amount > transaction_limit:
                violation_count += 1
                constraint_violations.append({
                    "type": "EXCEEDS_TRANSACTION_LIMIT",
                    "transaction_id": f"{record.get('sheet_name', '')}_row_{record.get('row_number', '')}",
                    "amount": amount,
                    "limit": transaction_limit,
                    "description": f"Transaction ${amount:,.2f} exceeds individual transaction limit"
                })
        
        # Check daily aggregate limit
        total_amount = sum(float(record.get("amount", 0)) for record in records)
        if daily_limit and total_amount > daily_limit:
            constraint_violations.append({
                "type": "EXCEEDS_DAILY_LIMIT",
                "total_amount": total_amount,
                "limit": daily_limit,
                "description": f"Total amount ${total_amount:,.2f} exceeds daily limit of ${daily_limit:,.2f}"
            })
        
        risk_report["risk_factors"]["constraint_violations"] = constraint_violations
        
        if constraint_violations:
            risk_report["risk_assessment"]["compliance_status"] = "NON_COMPLIANT"
    
    def _calculate_overall_risk(self, risk_report: Dict):
        """Calculate overall risk score and level."""
        total_risk_score = 0.0
        
        # Sum up risk scores from all categories
        for category in ["amount_risks", "pattern_risks", "compliance_risks"]:
            for risk_factor in risk_report["risk_factors"][category]:
                total_risk_score += risk_factor.get("risk_score", 0)
        
        # Add constraint violation penalties
        constraint_violations = risk_report["risk_factors"]["constraint_violations"]
        if constraint_violations:
            total_risk_score += len(constraint_violations) * 2.0
        
        # Normalize risk score (0-10 scale)
        risk_report["risk_assessment"]["overall_risk_score"] = min(10.0, total_risk_score)
        
        # Determine risk level
        if total_risk_score >= 7.0:
            risk_report["risk_assessment"]["risk_level"] = "CRITICAL"
        elif total_risk_score >= 4.0:
            risk_report["risk_assessment"]["risk_level"] = "HIGH"
        elif total_risk_score >= 2.0:
            risk_report["risk_assessment"]["risk_level"] = "MEDIUM"
        else:
            risk_report["risk_assessment"]["risk_level"] = "LOW"
    
    def _generate_recommendations(self, risk_report: Dict, user_constraints: Dict):
        """Generate actionable recommendations based on risk analysis."""
        recommendations = []
        
        risk_level = risk_report["risk_assessment"]["risk_level"]
        
        if risk_level in ["HIGH", "CRITICAL"]:
            recommendations.append("Manual review required before processing any payments")
            recommendations.append("Consider implementing additional approval workflows")
        
        if risk_report["flagged_transactions"]:
            recommendations.append(f"Review {len(risk_report['flagged_transactions'])} flagged transactions before proceeding")
        
        if risk_report["risk_factors"]["constraint_violations"]:
            recommendations.append("Address constraint violations before payment execution")
        
        # Specific recommendations based on risk factors
        for category, risks in risk_report["risk_factors"].items():
            for risk in risks:
                if risk.get("type") == "MISSING_REQUIRED_INFO":
                    recommendations.append("Ensure all transactions have complete recipient and description information")
                elif risk.get("type") == "HIGH_VALUE_TRANSACTIONS":
                    recommendations.append("Implement enhanced due diligence for high-value transactions")
                elif risk.get("type") == "MULTI_CURRENCY":
                    recommendations.append("Verify foreign exchange compliance and rates for multi-currency transactions")
        
        if not recommendations:
            recommendations.append("Risk assessment completed - no significant risks identified")
            recommendations.append("Proceed with standard payment processing workflow")
        
        risk_report["recommendations"] = recommendations
