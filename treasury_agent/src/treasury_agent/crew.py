from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from treasury_agent.tools.excel_parser_tool import ExcelParserTool
from treasury_agent.tools.risk_assessment_tool import RiskAssessmentTool
from treasury_agent.tools.payment_formatter_tool import PaymentFormatterTool
from treasury_agent.tools.investment_analyzer_tool import InvestmentAnalyzerTool
from treasury_agent.tools.hitl_interface_tool import HitlInterfaceTool

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

@CrewBase
class TreasuryAgent():
    """Treasury Manager AI Agent Crew - Automates financial processes with HITL checkpoints"""

    agents: List[BaseAgent]
    tasks: List[Task]

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    @agent
    def manager_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['manager_agent'], # type: ignore[index]
            tools=[ExcelParserTool(), HitlInterfaceTool()],
            verbose=True
        )

    @agent
    def risk_assessor_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['risk_assessor_agent'], # type: ignore[index]
            tools=[RiskAssessmentTool()],
            verbose=True
        )

    @agent
    def payment_specialist_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['payment_specialist_agent'], # type: ignore[index]
            tools=[PaymentFormatterTool()],
            verbose=True
        )

    @agent
    def investment_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['investment_agent'], # type: ignore[index]
            tools=[InvestmentAnalyzerTool()],
            verbose=True
        )

    # Treasury Manager AI Agent Tasks
    # Hierarchical workflow with Manager Agent coordinating specialized agents
    @task
    def excel_parsing_task(self) -> Task:
        return Task(
            config=self.tasks_config['excel_parsing_task'], # type: ignore[index]
            agent=self.manager_agent
        )

    @task
    def risk_assessment_task(self) -> Task:
        return Task(
            config=self.tasks_config['risk_assessment_task'], # type: ignore[index]
            agent=self.risk_assessor_agent
        )

    @task
    def payment_proposal_task(self) -> Task:
        return Task(
            config=self.tasks_config['payment_proposal_task'], # type: ignore[index]
            agent=self.payment_specialist_agent,
            context=[self.risk_assessment_task]
        )

    @task
    def investment_allocation_task(self) -> Task:
        return Task(
            config=self.tasks_config['investment_allocation_task'], # type: ignore[index]
            agent=self.investment_agent
        )

    @task
    def workflow_orchestration_task(self) -> Task:
        return Task(
            config=self.tasks_config['workflow_orchestration_task'], # type: ignore[index]
            agent=self.manager_agent,
            context=[self.payment_proposal_task, self.investment_allocation_task]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Treasury Manager AI Agent crew with hierarchical orchestration"""
        # Using hierarchical process with Manager Agent coordinating specialized agents
        # https://docs.crewai.com/concepts/processes#hierarchical-process

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.hierarchical,
            manager_agent=self.manager_agent,
            verbose=True,
            memory=True,  # Enable memory for context retention across tasks
            # Knowledge sources for financial regulations and compliance
            # https://docs.crewai.com/concepts/knowledge#what-is-knowledge
        )
