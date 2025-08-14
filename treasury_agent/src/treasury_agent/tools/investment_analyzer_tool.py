from crewai.tools import BaseTool
from typing import Type, Dict, Any, List
from pydantic import BaseModel, Field
import json
import datetime
import uuid
from decimal import Decimal, ROUND_HALF_UP


class InvestmentAnalyzerInput(BaseModel):
    """Input schema for InvestmentAnalyzerTool."""
    available_funds: float = Field(..., description="Amount of funds available for investment after payment execution")
    user_investment_preferences: Dict[str, Any] = Field(
        default={}, 
        description="User investment preferences including risk tolerance, asset allocation, investment goals"
    )
    payment_execution_result: str = Field(
        default="", 
        description="JSON string containing payment execution results and remaining balance"
    )


class InvestmentAnalyzerTool(BaseTool):
    name: str = "Investment Allocation Analyzer"
    description: str = (
        "Analyzes available funds after payment execution and generates investment allocation recommendations "
        "across fiat savings, crypto/DeFi opportunities, and liquidity products based on user preferences, "
        "risk tolerance, and market conditions. Creates structured investment plans for HITL approval."
    )
    args_schema: Type[BaseModel] = InvestmentAnalyzerInput

    def _run(self, available_funds: float, user_investment_preferences: Dict[str, Any] = None, payment_execution_result: str = "") -> str:
        """
        Generate investment allocation recommendations based on available funds and user preferences.
        
        Args:
            available_funds: Amount available for investment
            user_investment_preferences: User investment goals and risk preferences
            payment_execution_result: Results from payment execution
            
        Returns:
            JSON string containing structured investment allocation plan
        """
        try:
            if user_investment_preferences is None:
                user_investment_preferences = {}
                
            # Parse payment execution result if provided
            payment_result = {}
            if payment_execution_result:
                try:
                    payment_result = json.loads(payment_execution_result)
                except:
                    payment_result = {}
            
            # Generate unique investment plan ID
            investment_plan_id = str(uuid.uuid4())
            
            # Initialize investment allocation plan
            investment_plan = {
                "investment_plan_id": investment_plan_id,
                "timestamp": datetime.datetime.now().isoformat(),
                "status": "PENDING_APPROVAL",
                "available_funds": self._format_currency(available_funds),
                "user_preferences": user_investment_preferences,
                "allocation_summary": {
                    "total_allocated": 0.0,
                    "emergency_reserve": 0.0,
                    "investment_categories": {
                        "fiat_savings": {"allocation": 0.0, "percentage": 0.0},
                        "crypto_defi": {"allocation": 0.0, "percentage": 0.0},
                        "liquidity_products": {"allocation": 0.0, "percentage": 0.0}
                    }
                },
                "recommended_investments": [],
                "risk_assessment": {
                    "overall_risk_level": "MODERATE",
                    "diversification_score": 0.0,
                    "liquidity_ratio": 0.0
                },
                "approval_requirements": {
                    "requires_review": True,
                    "minimum_approval_level": "STANDARD",
                    "approval_deadline": None
                },
                "execution_timeline": {
                    "immediate_investments": [],
                    "scheduled_investments": [],
                    "contingent_investments": []
                },
                "compliance_checks": {
                    "regulatory_compliance": "PENDING",
                    "risk_limits_check": "PENDING",
                    "diversification_check": "PENDING"
                }
            }
            
            if available_funds <= 0:
                investment_plan["status"] = "NO_FUNDS_AVAILABLE"
                investment_plan["allocation_summary"]["message"] = "No funds available for investment allocation"
                return json.dumps(investment_plan, indent=2)
            
            # Analyze and create investment allocation
            self._calculate_emergency_reserve(investment_plan, available_funds, user_investment_preferences)
            self._determine_risk_profile(investment_plan, user_investment_preferences)
            self._allocate_funds(investment_plan, available_funds, user_investment_preferences)
            self._generate_investment_recommendations(investment_plan)
            self._assess_investment_risks(investment_plan)
            self._determine_approval_requirements(investment_plan, user_investment_preferences)
            self._create_execution_timeline(investment_plan)
            
            return json.dumps(investment_plan, indent=2)
            
        except Exception as e:
            error_plan = {
                "investment_plan_id": str(uuid.uuid4()),
                "timestamp": datetime.datetime.now().isoformat(),
                "status": "ERROR",
                "error": str(e),
                "available_funds": available_funds
            }
            return json.dumps(error_plan, indent=2)
    
    def _calculate_emergency_reserve(self, plan: Dict, available_funds: float, preferences: Dict):
        """Calculate recommended emergency reserve based on user preferences."""
        # Default emergency reserve: 10% of available funds or user preference
        reserve_percentage = preferences.get("emergency_reserve_percentage", 0.10)
        min_reserve = preferences.get("minimum_emergency_reserve", 1000.0)
        
        emergency_reserve = max(available_funds * reserve_percentage, min_reserve)
        emergency_reserve = min(emergency_reserve, available_funds * 0.30)  # Cap at 30%
        
        plan["allocation_summary"]["emergency_reserve"] = self._format_currency(emergency_reserve)
        
        # Reduce available funds for investment allocation
        plan["investable_funds"] = available_funds - emergency_reserve
    
    def _determine_risk_profile(self, plan: Dict, preferences: Dict):
        """Determine user's investment risk profile."""
        risk_tolerance = preferences.get("risk_tolerance", "moderate").lower()
        
        risk_profiles = {
            "conservative": {
                "fiat_allocation": 0.70,
                "crypto_allocation": 0.10,
                "liquidity_allocation": 0.20,
                "risk_level": "LOW"
            },
            "moderate": {
                "fiat_allocation": 0.50,
                "crypto_allocation": 0.30,
                "liquidity_allocation": 0.20,
                "risk_level": "MODERATE"
            },
            "aggressive": {
                "fiat_allocation": 0.30,
                "crypto_allocation": 0.50,
                "liquidity_allocation": 0.20,
                "risk_level": "HIGH"
            }
        }
        
        # Use moderate as default if invalid risk tolerance provided
        profile = risk_profiles.get(risk_tolerance, risk_profiles["moderate"])
        
        plan["risk_profile"] = profile
        plan["risk_assessment"]["overall_risk_level"] = profile["risk_level"]
    
    def _allocate_funds(self, plan: Dict, available_funds: float, preferences: Dict):
        """Allocate funds across investment categories based on risk profile and preferences."""
        investable_funds = plan["investable_funds"]
        risk_profile = plan["risk_profile"]
        
        # Apply custom allocations if specified by user
        custom_allocations = preferences.get("custom_allocations", {})
        
        fiat_percentage = custom_allocations.get("fiat_percentage", risk_profile["fiat_allocation"])
        crypto_percentage = custom_allocations.get("crypto_percentage", risk_profile["crypto_allocation"])
        liquidity_percentage = custom_allocations.get("liquidity_percentage", risk_profile["liquidity_allocation"])
        
        # Normalize percentages to ensure they sum to 1.0
        total_percentage = fiat_percentage + crypto_percentage + liquidity_percentage
        if total_percentage > 0:
            fiat_percentage /= total_percentage
            crypto_percentage /= total_percentage
            liquidity_percentage /= total_percentage
        
        # Calculate allocations
        fiat_allocation = investable_funds * fiat_percentage
        crypto_allocation = investable_funds * crypto_percentage
        liquidity_allocation = investable_funds * liquidity_percentage
        
        # Update allocation summary
        categories = plan["allocation_summary"]["investment_categories"]
        
        categories["fiat_savings"]["allocation"] = self._format_currency(fiat_allocation)
        categories["fiat_savings"]["percentage"] = round(fiat_percentage * 100, 1)
        
        categories["crypto_defi"]["allocation"] = self._format_currency(crypto_allocation)
        categories["crypto_defi"]["percentage"] = round(crypto_percentage * 100, 1)
        
        categories["liquidity_products"]["allocation"] = self._format_currency(liquidity_allocation)
        categories["liquidity_products"]["percentage"] = round(liquidity_percentage * 100, 1)
        
        plan["allocation_summary"]["total_allocated"] = self._format_currency(investable_funds)
    
    def _generate_investment_recommendations(self, plan: Dict):
        """Generate specific investment recommendations for each category."""
        categories = plan["allocation_summary"]["investment_categories"]
        recommendations = []
        
        # Fiat Savings Recommendations
        fiat_amount = categories["fiat_savings"]["allocation"]
        if fiat_amount > 0:
            fiat_recommendations = self._get_fiat_investment_options(fiat_amount)
            recommendations.extend(fiat_recommendations)
        
        # Crypto/DeFi Recommendations
        crypto_amount = categories["crypto_defi"]["allocation"]
        if crypto_amount > 0:
            crypto_recommendations = self._get_crypto_investment_options(crypto_amount)
            recommendations.extend(crypto_recommendations)
        
        # Liquidity Products Recommendations
        liquidity_amount = categories["liquidity_products"]["allocation"]
        if liquidity_amount > 0:
            liquidity_recommendations = self._get_liquidity_investment_options(liquidity_amount)
            recommendations.extend(liquidity_recommendations)
        
        plan["recommended_investments"] = recommendations
    
    def _get_fiat_investment_options(self, amount: float) -> List[Dict]:
        """Generate fiat investment recommendations."""
        recommendations = []
        
        if amount >= 1000:
            recommendations.append({
                "investment_id": str(uuid.uuid4()),
                "category": "fiat_savings",
                "investment_type": "High-Yield Savings Account",
                "allocation": self._format_currency(amount * 0.6),
                "expected_return": "4.5-5.5% APY",
                "risk_level": "LOW",
                "liquidity": "HIGH",
                "minimum_investment": 1000,
                "description": "FDIC-insured high-yield savings account for capital preservation",
                "execution_priority": 1
            })
            
            recommendations.append({
                "investment_id": str(uuid.uuid4()),
                "category": "fiat_savings",
                "investment_type": "Treasury Bills (T-Bills)",
                "allocation": self._format_currency(amount * 0.4),
                "expected_return": "5.0-5.5% APY",
                "risk_level": "VERY_LOW",
                "liquidity": "MEDIUM",
                "minimum_investment": 100,
                "description": "Short-term government securities with guaranteed returns",
                "execution_priority": 2
            })
        else:
            recommendations.append({
                "investment_id": str(uuid.uuid4()),
                "category": "fiat_savings",
                "investment_type": "Money Market Account",
                "allocation": self._format_currency(amount),
                "expected_return": "4.0-5.0% APY",
                "risk_level": "LOW",
                "liquidity": "HIGH",
                "minimum_investment": 100,
                "description": "Liquid savings with competitive interest rates",
                "execution_priority": 1
            })
        
        return recommendations
    
    def _get_crypto_investment_options(self, amount: float) -> List[Dict]:
        """Generate crypto/DeFi investment recommendations."""
        recommendations = []
        
        if amount >= 500:
            recommendations.append({
                "investment_id": str(uuid.uuid4()),
                "category": "crypto_defi",
                "investment_type": "Bitcoin (BTC)",
                "allocation": self._format_currency(amount * 0.4),
                "expected_return": "Variable (High volatility)",
                "risk_level": "HIGH",
                "liquidity": "HIGH",
                "minimum_investment": 10,
                "description": "Leading cryptocurrency for portfolio diversification",
                "execution_priority": 1
            })
            
            recommendations.append({
                "investment_id": str(uuid.uuid4()),
                "category": "crypto_defi",
                "investment_type": "Ethereum (ETH)",
                "allocation": self._format_currency(amount * 0.3),
                "expected_return": "Variable (High volatility)",
                "risk_level": "HIGH",
                "liquidity": "HIGH",
                "minimum_investment": 10,
                "description": "Smart contract platform with DeFi ecosystem exposure",
                "execution_priority": 2
            })
            
            recommendations.append({
                "investment_id": str(uuid.uuid4()),
                "category": "crypto_defi",
                "investment_type": "Stablecoin Yield Farming",
                "allocation": self._format_currency(amount * 0.3),
                "expected_return": "6-12% APY",
                "risk_level": "MEDIUM",
                "liquidity": "MEDIUM",
                "minimum_investment": 100,
                "description": "USDC/DAI liquidity provision for yield generation",
                "execution_priority": 3
            })
        else:
            recommendations.append({
                "investment_id": str(uuid.uuid4()),
                "category": "crypto_defi",
                "investment_type": "Diversified Crypto Index",
                "allocation": self._format_currency(amount),
                "expected_return": "Variable (Moderate volatility)",
                "risk_level": "MEDIUM_HIGH",
                "liquidity": "HIGH",
                "minimum_investment": 25,
                "description": "Diversified exposure to major cryptocurrencies",
                "execution_priority": 1
            })
        
        return recommendations
    
    def _get_liquidity_investment_options(self, amount: float) -> List[Dict]:
        """Generate liquidity product investment recommendations."""
        recommendations = []
        
        recommendations.append({
            "investment_id": str(uuid.uuid4()),
            "category": "liquidity_products",
            "investment_type": "Short-term CDs",
            "allocation": self._format_currency(amount * 0.5),
            "expected_return": "5.0-6.0% APY",
            "risk_level": "LOW",
            "liquidity": "LOW",
            "minimum_investment": 500,
            "description": "6-month certificates of deposit with guaranteed returns",
            "execution_priority": 1
        })
        
        recommendations.append({
            "investment_id": str(uuid.uuid4()),
            "category": "liquidity_products",
            "investment_type": "Money Market Funds",
            "allocation": self._format_currency(amount * 0.5),
            "expected_return": "4.5-5.5% APY",
            "risk_level": "LOW",
            "liquidity": "HIGH",
            "minimum_investment": 100,
            "description": "Professional money market fund management",
            "execution_priority": 2
        })
        
        return recommendations
    
    def _assess_investment_risks(self, plan: Dict):
        """Assess overall investment portfolio risks."""
        recommendations = plan["recommended_investments"]
        
        if not recommendations:
            return
        
        # Calculate diversification score
        categories = set(rec["category"] for rec in recommendations)
        diversification_score = len(categories) / 3.0  # 3 total categories
        
        # Calculate liquidity ratio
        high_liquidity = [rec for rec in recommendations if rec["liquidity"] == "HIGH"]
        liquidity_ratio = len(high_liquidity) / len(recommendations) if recommendations else 0
        
        # Assess overall risk
        risk_levels = [rec["risk_level"] for rec in recommendations]
        risk_counts = {
            "VERY_LOW": risk_levels.count("VERY_LOW"),
            "LOW": risk_levels.count("LOW"),
            "MEDIUM": risk_levels.count("MEDIUM") + risk_levels.count("MEDIUM_HIGH"),
            "HIGH": risk_levels.count("HIGH")
        }
        
        plan["risk_assessment"]["diversification_score"] = round(diversification_score * 100, 1)
        plan["risk_assessment"]["liquidity_ratio"] = round(liquidity_ratio * 100, 1)
        plan["risk_assessment"]["risk_distribution"] = risk_counts
    
    def _determine_approval_requirements(self, plan: Dict, preferences: Dict):
        """Determine approval requirements for investment plan."""
        total_amount = plan["allocation_summary"]["total_allocated"]
        risk_level = plan["risk_assessment"]["overall_risk_level"]
        
        approval_reqs = plan["approval_requirements"]
        
        # Set approval level based on amount and risk
        if total_amount > 100000 or risk_level == "HIGH":
            approval_reqs["minimum_approval_level"] = "HIGH"
            approval_reqs["requires_review"] = True
        elif total_amount > 50000:
            approval_reqs["minimum_approval_level"] = "MEDIUM"
        else:
            approval_reqs["minimum_approval_level"] = "STANDARD"
        
        # Set approval deadline
        deadline = datetime.datetime.now() + datetime.timedelta(hours=48)
        approval_reqs["approval_deadline"] = deadline.isoformat()
    
    def _create_execution_timeline(self, plan: Dict):
        """Create execution timeline for approved investments."""
        recommendations = plan["recommended_investments"]
        
        immediate = []
        scheduled = []
        contingent = []
        
        for rec in recommendations:
            if rec["execution_priority"] == 1:
                immediate.append({
                    "investment_id": rec["investment_id"],
                    "investment_type": rec["investment_type"],
                    "allocation": rec["allocation"],
                    "execution_window": "0-1 business days"
                })
            elif rec["execution_priority"] == 2:
                scheduled.append({
                    "investment_id": rec["investment_id"],
                    "investment_type": rec["investment_type"],
                    "allocation": rec["allocation"],
                    "execution_window": "2-3 business days"
                })
            else:
                contingent.append({
                    "investment_id": rec["investment_id"],
                    "investment_type": rec["investment_type"],
                    "allocation": rec["allocation"],
                    "execution_window": "Market dependent"
                })
        
        plan["execution_timeline"]["immediate_investments"] = immediate
        plan["execution_timeline"]["scheduled_investments"] = scheduled
        plan["execution_timeline"]["contingent_investments"] = contingent
    
    def _format_currency(self, amount: float) -> float:
        """Format currency amount to 2 decimal places."""
        return float(Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
