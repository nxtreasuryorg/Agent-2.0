"""Data Analyzer Tool for analyzing financial data and generating insights."""
from typing import Dict, Any, List, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import pandas as pd
import json

class DataAnalyzerInput(BaseModel):
    """Input schema for Data Analyzer Tool."""
    data: Dict[str, Any] = Field(description="Financial data to analyze")
    analysis_type: str = Field(default="comprehensive", description="Type of analysis to perform")
    constraints: Dict[str, Any] = Field(default={}, description="Analysis constraints")

class DataAnalyzerTool(BaseTool):
    name: str = "Data Analyzer Tool"
    description: str = """
    Analyze financial data to extract insights, patterns, and generate recommendations.
    Supports comprehensive analysis of payment data, risk assessment, and constraint validation.
    """
    args_schema: type[BaseModel] = DataAnalyzerInput

    def _run(self, data: Dict[str, Any], analysis_type: str = "comprehensive", 
             constraints: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Analyze financial data and return insights."""
        try:
            analysis_result = {
                "analysis_type": analysis_type,
                "timestamp": pd.Timestamp.now().isoformat(),
                "data_quality": self._assess_data_quality(data),
                "financial_summary": self._generate_financial_summary(data),
                "risk_indicators": self._identify_risk_indicators(data, constraints),
                "recommendations": self._generate_recommendations(data, constraints),
                "compliance_check": self._check_compliance(data, constraints)
            }
            
            return analysis_result
            
        except Exception as e:
            return {
                "error": str(e),
                "success": False,
                "analysis_type": analysis_type
            }
    
    def _assess_data_quality(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the quality and completeness of financial data."""
        quality_score = 100
        issues = []
        
        # Check for required fields in payment data
        if "payments" in data:
            payments = data["payments"]
            if not payments:
                quality_score -= 30
                issues.append("No payment data found")
            else:
                for i, payment in enumerate(payments):
                    if not payment.get("amount"):
                        quality_score -= 10
                        issues.append(f"Missing amount in payment {i+1}")
                    if not payment.get("recipient"):
                        quality_score -= 10
                        issues.append(f"Missing recipient in payment {i+1}")
        
        return {
            "quality_score": max(0, quality_score),
            "issues": issues,
            "completeness": "high" if quality_score > 80 else "medium" if quality_score > 50 else "low"
        }
    
    def _generate_financial_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of financial data."""
        summary = {
            "total_payments": 0,
            "total_amount": 0,
            "average_payment": 0,
            "currency_breakdown": {},
            "payment_categories": {}
        }
        
        if "payments" in data:
            payments = data["payments"]
            summary["total_payments"] = len(payments)
            
            amounts = []
            for payment in payments:
                amount = payment.get("amount", 0)
                amounts.append(amount)
                summary["total_amount"] += amount
                
                # Currency breakdown
                currency = payment.get("currency", "USD")
                summary["currency_breakdown"][currency] = summary["currency_breakdown"].get(currency, 0) + amount
                
                # Category breakdown
                category = payment.get("category", "general")
                summary["payment_categories"][category] = summary["payment_categories"].get(category, 0) + 1
            
            if amounts:
                summary["average_payment"] = sum(amounts) / len(amounts)
                summary["min_payment"] = min(amounts)
                summary["max_payment"] = max(amounts)
        
        return summary
    
    def _identify_risk_indicators(self, data: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Identify potential risk indicators in the financial data."""
        risk_indicators = {
            "high_value_transactions": [],
            "unusual_patterns": [],
            "constraint_violations": [],
            "overall_risk_level": "low"
        }
        
        if "payments" in data:
            payments = data["payments"]
            amounts = [p.get("amount", 0) for p in payments]
            
            if amounts:
                avg_amount = sum(amounts) / len(amounts)
                max_amount = max(amounts)
                
                # Check for high-value transactions (>3x average)
                for i, payment in enumerate(payments):
                    amount = payment.get("amount", 0)
                    if amount > avg_amount * 3:
                        risk_indicators["high_value_transactions"].append({
                            "payment_index": i,
                            "amount": amount,
                            "recipient": payment.get("recipient", "Unknown")
                        })
                
                # Check constraint violations
                single_limit = constraints.get("transaction_limits", {}).get("single", float('inf'))
                daily_limit = constraints.get("transaction_limits", {}).get("daily", float('inf'))
                
                total_amount = sum(amounts)
                if max_amount > single_limit:
                    risk_indicators["constraint_violations"].append(f"Single transaction limit exceeded: {max_amount} > {single_limit}")
                if total_amount > daily_limit:
                    risk_indicators["constraint_violations"].append(f"Daily limit exceeded: {total_amount} > {daily_limit}")
                
                # Determine overall risk level
                risk_score = 0
                risk_score += len(risk_indicators["high_value_transactions"]) * 2
                risk_score += len(risk_indicators["constraint_violations"]) * 5
                
                if risk_score > 10:
                    risk_indicators["overall_risk_level"] = "high"
                elif risk_score > 5:
                    risk_indicators["overall_risk_level"] = "medium"
        
        return risk_indicators
    
    def _generate_recommendations(self, data: Dict[str, Any], constraints: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on data analysis."""
        recommendations = []
        
        if "payments" in data:
            payments = data["payments"]
            if not payments:
                recommendations.append("No payments to process")
                return recommendations
            
            amounts = [p.get("amount", 0) for p in payments]
            total_amount = sum(amounts)
            
            # Check minimum balance
            min_balance = constraints.get("minimum_balance", 0)
            if total_amount > min_balance * 0.8:  # Using 80% threshold
                recommendations.append("Consider reviewing minimum balance requirements after payments")
            
            # Payment timing recommendations
            if len(payments) > 10:
                recommendations.append("Consider batching payments for efficiency")
            
            # High-value transaction recommendations
            max_amount = max(amounts) if amounts else 0
            avg_amount = sum(amounts) / len(amounts) if amounts else 0
            
            if max_amount > avg_amount * 5:
                recommendations.append("Review high-value transactions for additional approval")
            
            recommendations.append("All payments appear ready for processing")
        
        return recommendations
    
    def _check_compliance(self, data: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Check compliance with regulatory and business constraints."""
        compliance = {
            "status": "compliant",
            "violations": [],
            "warnings": [],
            "checks_performed": []
        }
        
        compliance["checks_performed"].append("Transaction limits validation")
        compliance["checks_performed"].append("Minimum balance validation")
        compliance["checks_performed"].append("Data completeness validation")
        
        if "payments" in data:
            payments = data["payments"]
            total_amount = sum(p.get("amount", 0) for p in payments)
            
            # Check transaction limits
            limits = constraints.get("transaction_limits", {})
            single_limit = limits.get("single", float('inf'))
            daily_limit = limits.get("daily", float('inf'))
            
            for payment in payments:
                amount = payment.get("amount", 0)
                if amount > single_limit:
                    compliance["violations"].append(f"Payment exceeds single transaction limit: {amount}")
            
            if total_amount > daily_limit:
                compliance["violations"].append(f"Total payments exceed daily limit: {total_amount}")
            
            # Check minimum balance
            min_balance = constraints.get("minimum_balance", 0)
            if total_amount > min_balance:
                compliance["warnings"].append("Payments may impact minimum balance requirements")
        
        if compliance["violations"]:
            compliance["status"] = "non-compliant"
        elif compliance["warnings"]:
            compliance["status"] = "compliant_with_warnings"
        
        return compliance
