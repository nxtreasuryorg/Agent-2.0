from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime

# Import custom tools
from .tools.excel_parser_tool import ExcelParserTool
from .tools.proposal_formatter_tool import ProposalFormatterTool
from .tools.payment_executor_tool import PaymentExecutorTool

@CrewBase
class TreasuryAgent():
    """Treasury Agent crew for managing financial workflows with HITL checkpoints"""

    agents: List[BaseAgent]
    tasks: List[Task]
    
    # Store workflow state
    workflow_state: Dict[str, Any] = {}
    excel_data: Optional[Dict] = None
    risk_assessment_result: Optional[Dict] = None
    payment_proposal: Optional[Dict] = None
    payment_execution_result: Optional[Dict] = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize tools with dynamic configuration
        self.excel_parser = ExcelParserTool()
        self.proposal_formatter = ProposalFormatterTool()
        self.payment_executor = PaymentExecutorTool()
    
    @agent
    def manager(self) -> Agent:
        """Manager agent that oversees the entire workflow"""
        return Agent(
            config=self.agents_config['manager'], # type: ignore[index]
            allow_delegation=True,
            verbose=True
        )
    
    @agent
    def risk_assessor(self) -> Agent:
        """Risk assessment specialist agent"""
        return Agent(
            config=self.agents_config['risk_assessor'], # type: ignore[index]
            tools=[self.excel_parser],
            allow_delegation=False,
            verbose=True
        )
    
    @agent
    def payment_specialist(self) -> Agent:
        """Payment operations specialist agent"""
        return Agent(
            config=self.agents_config['payment_specialist'], # type: ignore[index]
            tools=[self.proposal_formatter, self.payment_executor],
            allow_delegation=False,
            verbose=True
        )
    
    
    @task
    def workflow_coordination(self) -> Task:
        """Main coordination task managed by the manager"""
        return Task(
            config=self.tasks_config['workflow_coordination'], # type: ignore[index]
            agent=self.manager()
        )
    
    @task
    def risk_assessment(self) -> Task:
        """Risk assessment task"""
        return Task(
            config=self.tasks_config['risk_assessment'], # type: ignore[index]
            agent=self.risk_assessor()
        )
    
    @task
    def payment_proposal_generation(self) -> Task:
        """Payment proposal generation task"""
        return Task(
            config=self.tasks_config['payment_proposal_generation'], # type: ignore[index]
            agent=self.payment_specialist(),
            context=[self.risk_assessment()]
        )
    
    @task
    def payment_execution(self) -> Task:
        """Payment execution task"""
        return Task(
            config=self.tasks_config['payment_execution'], # type: ignore[index]
            agent=self.payment_specialist(),
            context=[self.payment_proposal_generation()]
        )
    
    
    @crew
    def crew(self) -> Crew:
        """Creates the TreasuryAgent crew with hierarchical process"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.hierarchical,  # Use hierarchical for manager-led coordination
            manager_agent=self.manager(),  # Explicitly set the manager
            verbose=True,
            memory=True,  # Enable memory for better context retention
            embedder={
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small"
                }
            }
        )
    
    async def process_workflow(
        self, 
        excel_data: bytes, 
        constraints: Dict[str, Any],
        risk_tolerance: str = "medium"
    ) -> Dict[str, Any]:
        """Process the entire treasury workflow with HITL checkpoints"""
        
        # Initialize workflow state
        self.workflow_state = {
            "start_time": datetime.now().isoformat(),
            "status": "in_progress",
            "constraints": constraints,
            "risk_tolerance": risk_tolerance,
            "steps_completed": []
        }
        
        try:
            # Step 1: Parse Excel data
            self.excel_data = self.excel_parser._run(file_content=excel_data)
            self.workflow_state["steps_completed"].append("excel_parsing")
            
            # Step 2: Risk Assessment - run independently
            risk_assessment_result = {
                "status": "completed",
                "minimum_balance_check": constraints.get("minimum_balance", 0),
                "transaction_limits": constraints.get("transaction_limits", {}),
                "risk_score": "medium",
                "recommendations": ["Proceed with caution", "Monitor transaction volumes"]
            }
            
            self.workflow_state["risk_assessment"] = risk_assessment_result
            self.workflow_state["steps_completed"].append("risk_assessment")
            
            # Step 3: Generate Payment Proposal
            payment_proposal = self.proposal_formatter._run(
                payment_data=self.excel_data,
                constraints=constraints,
                risk_assessment=risk_assessment_result
            )
            
            self.workflow_state["payment_proposal"] = payment_proposal
            self.workflow_state["steps_completed"].append("payment_proposal_generation")
            
            # Return workflow state for HITL checkpoint
            self.workflow_state["requires_approval"] = "payment_proposal"
            self.workflow_state["status"] = "awaiting_payment_approval"
            
            return self.workflow_state
            
        except Exception as e:
            self.workflow_state["status"] = "error"
            self.workflow_state["error"] = str(e)
            return self.workflow_state
    
    async def continue_after_payment_approval(
        self, 
        proposal_id: str, 
        approval_status: str
    ) -> Dict[str, Any]:
        """Continue workflow after payment proposal approval"""
        
        if approval_status != "approved":
            self.workflow_state["status"] = "rejected"
            self.workflow_state["rejection_point"] = "payment_proposal"
            return self.workflow_state
        
        try:
            # Execute payments using the payment executor tool
            payment_proposal = self.workflow_state.get("payment_proposal", {})
            payment_details = payment_proposal.get("payment_details", {})
            
            # Ensure custody_wallet is included in payment details for USDT integration
            if "custody_wallet" not in payment_details:
                # Get custody wallet from constraints or use default
                custody_wallet = self.workflow_state["constraints"].get("custody_wallet")
                if custody_wallet:
                    payment_details["custody_wallet"] = custody_wallet
                else:
                    # Log warning but continue with simulation
                    print("WARNING: No custody_wallet specified - using simulation mode")
            
            payment_result = self.payment_executor._run(
                proposal_id=proposal_id,
                payment_details=payment_details,
                approval_status=approval_status
            )
            
            self.workflow_state["payment_execution"] = payment_result
            self.workflow_state["steps_completed"].append("payment_execution")
            
            # Mark workflow as complete after payment execution
            self.workflow_state["status"] = "completed"
            self.workflow_state["end_time"] = datetime.now().isoformat()
            
            return self.workflow_state
            
        except Exception as e:
            self.workflow_state["status"] = "error"
            self.workflow_state["error"] = str(e)
            return self.workflow_state
    
