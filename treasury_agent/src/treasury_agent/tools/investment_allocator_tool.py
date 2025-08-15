"""Investment Allocator Tool for generating investment allocations and recommendations."""
from typing import Dict, Any, List, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import uuid

# Import configuration
from ..config.config_loader import get_config

class InvestmentAllocatorInput(BaseModel):
    """Input schema for Investment Allocator Tool."""
    remaining_balance: float = Field(description="Remaining balance after payments")
    investment_preferences: Dict[str, Any] = Field(description="User investment preferences")
    risk_tolerance: str = Field(default="medium", description="Risk tolerance level")
    execution_mode: bool = Field(default=False, description="Whether to execute investments or just plan")
    investment_plan: Optional[Dict[str, Any]] = Field(default=None, description="Investment plan to execute")

class InvestmentAllocatorTool(BaseTool):
    name: str = "Investment Allocator Tool (SIMULATION MODE)"
    description: str = """
    SIMULATION ONLY: Create investment allocation plans for testing purposes.
    NO ACTUAL INVESTMENTS ARE MADE - This tool only generates mock investment plans.
    In production, this would interface with real investment platforms.
    """
    args_schema: type[BaseModel] = InvestmentAllocatorInput
    
    def __init__(self, **kwargs):
        """Initialize with configuration from config file."""
        super().__init__(**kwargs)
        config = get_config()
        self.execution_fee_rate = config.get_execution_fee_rate()
        self.min_recommendation_threshold = config.get_min_threshold()

    def _run(self, remaining_balance: float, investment_preferences: Dict[str, Any], 
             risk_tolerance: str = "medium", execution_mode: bool = False, 
             investment_plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """SIMULATION: Create mock investment allocation plan or execute investment plan for testing purposes only."""
        try:
            if execution_mode and investment_plan:
                return self._execute_investment_plan(investment_plan)
            
            print(f"[SIMULATION MODE] Creating investment plan for balance: ${remaining_balance}")
            print("[SIMULATION MODE] NO ACTUAL INVESTMENTS WILL BE MADE")
            
            # Generate unique plan ID
            plan_id = f"SIMULATION-INV-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            # Define investment options based on requirements
            investment_options = {
                "liquidity_products": {
                    "name": "Liquidity Products",
                    "risk_level": "low",
                    "expected_yield": 2.5,
                    "liquidity": "high",
                    "min_investment": 1000,
                    "lock_period_days": 0,
                    "description": "Highly liquid money market funds with daily access"
                },
                "stablecoins": {
                    "name": "Stablecoins (USDC/USDT)",
                    "risk_level": "low-medium",
                    "expected_yield": 4.5,
                    "liquidity": "high",
                    "min_investment": 100,
                    "lock_period_days": 0,
                    "description": "USD-pegged cryptocurrencies earning yield through lending"
                },
                "time_deposit": {
                    "name": "Short-term Time Deposit",
                    "risk_level": "low",
                    "expected_yield": 3.5,
                    "liquidity": "medium",
                    "min_investment": 5000,
                    "lock_period_days": 30,
                    "description": "Traditional bank deposit with fixed returns"
                },
                "defi_yield": {
                    "name": "DeFi Yield Farming",
                    "risk_level": "high",
                    "expected_yield": 8.0,
                    "liquidity": "medium",
                    "min_investment": 500,
                    "lock_period_days": 7,
                    "description": "Decentralized finance yield optimization strategies"
                }
            }
            
            # Filter options based on risk tolerance
            risk_mapping = {
                "low": ["liquidity_products", "time_deposit"],
                "medium": ["liquidity_products", "stablecoins", "time_deposit"],
                "high": ["liquidity_products", "stablecoins", "time_deposit", "defi_yield"]
            }
            
            available_options = risk_mapping.get(risk_tolerance, risk_mapping["medium"])
            
            # Create allocation strategy
            allocations = []
            total_allocated = 0
            
            # Default allocation percentages based on risk tolerance
            allocation_strategy = {
                "low": {"liquidity_products": 0.7, "time_deposit": 0.3},
                "medium": {"liquidity_products": 0.4, "stablecoins": 0.4, "time_deposit": 0.2},
                "high": {"liquidity_products": 0.3, "stablecoins": 0.3, "time_deposit": 0.2, "defi_yield": 0.2}
            }
            
            strategy = allocation_strategy.get(risk_tolerance, allocation_strategy["medium"])
            
            # Create allocations based on strategy
            for option_key in available_options:
                if option_key in strategy and option_key in investment_options:
                    option = investment_options[option_key]
                    allocation_amount = remaining_balance * strategy[option_key]
                    
                    # Check minimum investment requirement
                    if allocation_amount >= option["min_investment"]:
                        print(f"[SIMULATION] Mock allocation: ${allocation_amount} to {option['name']}")
                        allocation = {
                            "allocation_id": f"SIMULATION-ALLOC-{uuid.uuid4().hex[:8]}",
                            "investment_type": option["name"],
                            "amount": round(allocation_amount, 2),
                            "percentage": round(strategy[option_key] * 100, 1),
                            "expected_yield": option["expected_yield"],
                            "expected_return": round(allocation_amount * (option["expected_yield"] / 100), 2),
                            "risk_level": option["risk_level"],
                            "liquidity": option["liquidity"],
                            "lock_period_days": option["lock_period_days"],
                            "maturity_date": (datetime.now() + timedelta(days=option["lock_period_days"])).isoformat() if option["lock_period_days"] > 0 else None,
                            "description": option["description"],
                            "simulation_note": "NO ACTUAL INVESTMENT EXECUTED - TESTING ONLY"
                        }
                        allocations.append(allocation)
                        total_allocated += allocation_amount
            
            # Calculate overall metrics
            weighted_yield = sum(a["amount"] * a["expected_yield"] for a in allocations) / total_allocated if total_allocated > 0 else 0
            total_expected_return = sum(a["expected_return"] for a in allocations)
            
            # Create investment plan
            investment_plan = {
                "plan_id": plan_id,
                "type": "investment_plan",
                "timestamp": datetime.now().isoformat(),
                "status": "pending_approval",
                
                "allocation_summary": {
                    "total_available": remaining_balance,
                    "total_allocated": round(total_allocated, 2),
                    "unallocated": round(remaining_balance - total_allocated, 2),
                    "number_of_investments": len(allocations)
                },
                
                "risk_profile": {
                    "tolerance": risk_tolerance,
                    "diversification_score": min(len(allocations) * 25, 100),  # Simple diversification metric
                    "overall_risk": risk_tolerance
                },
                
                "expected_returns": {
                    "weighted_average_yield": round(weighted_yield, 2),
                    "total_expected_return": round(total_expected_return, 2),
                    "return_period": "annual",
                    "currency": "USD"
                },
                
                "allocations": allocations,
                
                "liquidity_analysis": {
                    "immediate_access": sum(a["amount"] for a in allocations if a["liquidity"] == "high"),
                    "locked_funds": sum(a["amount"] for a in allocations if a["lock_period_days"] > 0),
                    "average_lock_period": sum(a["lock_period_days"] * a["amount"] for a in allocations) / total_allocated if total_allocated > 0 else 0
                },
                
                "recommendations": [],
                
                "approval_metadata": {
                    "requires_approval": True,
                    "approval_level": "standard",
                    "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
                    "approval_actions": ["approve", "reject", "modify"]
                }
            }
            
            # Add recommendations
            if investment_plan["allocation_summary"]["unallocated"] > self.min_recommendation_threshold:
                investment_plan["recommendations"].append(
                    f"Consider allocating the remaining ${investment_plan['allocation_summary']['unallocated']:.2f} to increase returns"
                )
            
            if risk_tolerance == "low" and weighted_yield < 3:
                investment_plan["recommendations"].append(
                    "Consider slightly increasing risk tolerance for better returns while maintaining safety"
                )
            
            if len(allocations) < 2:
                investment_plan["recommendations"].append(
                    "Consider diversifying across more investment types to reduce concentration risk"
                )
            
            investment_plan["success"] = True
            investment_plan["simulation_mode"] = True
            investment_plan["disclaimer"] = "NO ACTUAL INVESTMENTS WERE MADE - THIS IS A SIMULATION FOR TESTING PURPOSES ONLY"
            investment_plan["status"] = "simulation_plan_created"
            
            print("[SIMULATION MODE] Investment plan created - NO ACTUAL INVESTMENTS MADE")
            return investment_plan
            
        except Exception as e:
            return {
                "error": str(e),
                "success": False,
                "metadata": {"error_type": type(e).__name__}
            }
    
    def _execute_investment_plan(self, investment_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an approved investment plan in simulation mode."""
        try:
            print("[SIMULATION MODE] Executing investment plan - NO ACTUAL INVESTMENTS MADE")
            
            plan_id = investment_plan.get("plan_id", f"EXEC-{uuid.uuid4().hex[:8]}")
            allocations = investment_plan.get("allocations", [])
            
            executed_allocations = []
            total_executed = 0
            execution_fees = 0
            
            for allocation in allocations:
                # Simulate execution with mock confirmation
                executed_allocation = {
                    "allocation_id": allocation.get("allocation_id"),
                    "investment_type": allocation.get("investment_type"),
                    "amount": allocation.get("amount", 0),
                    "status": "simulation_executed",
                    "execution_id": f"SIMULATION-EXEC-{uuid.uuid4().hex[:8]}",
                    "executed_at": datetime.now().isoformat(),
                    "confirmation_code": f"SIM-{uuid.uuid4().hex[:6].upper()}",
                    "expected_yield": allocation.get("expected_yield", 0),
                    "maturity_date": allocation.get("maturity_date"),
                    "simulation_note": "NO ACTUAL INVESTMENT EXECUTED - TESTING ONLY"
                }
                
                executed_allocations.append(executed_allocation)
                total_executed += allocation.get("amount", 0)
                execution_fees += allocation.get("amount", 0) * self.execution_fee_rate  # Configurable fee simulation
            
            execution_result = {
                "plan_id": plan_id,
                "execution_id": f"SIMULATION-INV-EXEC-{uuid.uuid4().hex[:8]}",
                "status": "simulation_completed",
                "executed_at": datetime.now().isoformat(),
                "total_allocated": total_executed,
                "execution_fees": execution_fees,
                "net_invested": total_executed - execution_fees,
                "executed_allocations": executed_allocations,
                "summary": {
                    "total_investments": len(executed_allocations),
                    "successful_executions": len([a for a in executed_allocations if a["status"] == "simulation_executed"]),
                    "failed_executions": 0,
                    "total_amount": total_executed
                },
                "simulation_mode": True,
                "disclaimer": "NO ACTUAL INVESTMENTS WERE EXECUTED - THIS IS A SIMULATION FOR TESTING PURPOSES ONLY",
                "success": True
            }
            
            print(f"[SIMULATION MODE] Investment execution completed - {len(executed_allocations)} investments simulated")
            return execution_result
            
        except Exception as e:
            return {
                "error": str(e),
                "success": False,
                "plan_id": investment_plan.get("plan_id", "unknown"),
                "status": "execution_error",
                "metadata": {"error_type": type(e).__name__}
            }
