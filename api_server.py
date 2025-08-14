#!/usr/bin/env python3
"""
Treasury Manager AI Agent API Server

Implements the full API contract for Treasury Manager AI Agent system.
Provides RESTful endpoints for Excel upload, payment processing, HITL checkpoints,
and investment allocation workflows.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import tempfile

# Import Treasury Agent Crew and Tools
from treasury_agent.src.treasury_agent.crew import TreasuryAgent
from treasury_agent.src.treasury_agent.tools.excel_parser_tool import ExcelParserTool
from treasury_agent.src.treasury_agent.tools.risk_assessment_tool import RiskAssessmentTool
from treasury_agent.src.treasury_agent.tools.payment_formatter_tool import PaymentFormatterTool
from treasury_agent.src.treasury_agent.tools.investment_analyzer_tool import InvestmentAnalyzerTool
from treasury_agent.src.treasury_agent.tools.hitl_interface_tool import HitlInterfaceTool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for client integration

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# In-memory storage for demo (replace with database in production)
proposal_storage = {}
execution_storage = {}

# Allowed file extensions
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}


def allowed_file(filename):
    """Check if uploaded file has allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def error_response(message: str, status_code: int = 400) -> tuple:
    """Generate consistent error response."""
    return jsonify({
        "error": message,
        "success": False
    }), status_code


def success_response(data: Dict[str, Any], status_code: int = 200) -> tuple:
    """Generate consistent success response."""
    response_data = {"success": True}
    response_data.update(data)
    return jsonify(response_data), status_code


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


@app.route('/submit_request', methods=['POST'])
def submit_request():
    """
    Submit Excel file and JSON configuration for treasury workflow processing.
    
    Expected multipart/form-data:
    - excel: Excel file
    - json: JSON configuration string
    
    Returns proposal_id for subsequent workflow steps.
    """
    try:
        # Validate request
        if 'excel' not in request.files or 'json' not in request.form:
            return error_response("Missing required fields: 'excel' file and 'json' configuration")
        
        excel_file = request.files['excel']
        json_config_str = request.form['json']
        
        # Validate Excel file
        if excel_file.filename == '' or not allowed_file(excel_file.filename):
            return error_response("Invalid Excel file. Only .xlsx and .xls files are allowed.")
        
        # Parse JSON configuration
        try:
            json_config = json.loads(json_config_str)
            user_id = json_config.get('user_id', 'unknown')
            risk_config = json_config.get('risk_config', {})
            user_notes = json_config.get('user_notes', '')
        except json.JSONDecodeError:
            return error_response("Invalid JSON configuration format")
        
        # Save uploaded file temporarily
        filename = secure_filename(excel_file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{filename}")
        excel_file.save(file_path)
        
        # Generate unique proposal ID
        proposal_id = str(uuid.uuid4())
        
        # Initialize Treasury Agent Crew
        treasury_crew = TreasuryAgent()
        
        # Prepare workflow inputs
        workflow_inputs = {
            'excel_file_path': file_path,
            'user_constraints': {
                'minimum_balance': risk_config.get('min_balance_usd', 0),
                'transaction_limit': risk_config.get('transaction_limits', {}).get('single'),
                'daily_limit': risk_config.get('transaction_limits', {}).get('daily'),
                'user_id': user_id,
                'user_notes': user_notes
            },
            'proposal_id': proposal_id
        }
        
        # Execute crew workflow (Excel parsing and risk assessment)
        logger.info(f"Starting treasury workflow for proposal {proposal_id}")
        crew_result = treasury_crew.crew().kickoff(inputs=workflow_inputs)
        
        # Process crew results and generate payment proposal
        excel_parser = ExcelParserTool()
        risk_assessor = RiskAssessmentTool()
        payment_formatter = PaymentFormatterTool()
        
        # Parse Excel data
        excel_result = excel_parser._run(file_path, workflow_inputs['user_constraints'])
        
        # Perform risk assessment
        risk_result = risk_assessor._run(excel_result, workflow_inputs['user_constraints'])
        
        # Generate payment proposal
        payment_proposal = payment_formatter._run(excel_result, risk_result, workflow_inputs['user_constraints'])
        
        # Store proposal data
        proposal_storage[proposal_id] = {
            'proposal_id': proposal_id,
            'user_id': user_id,
            'created_at': datetime.now().isoformat(),
            'status': 'PENDING_PAYMENT_APPROVAL',
            'excel_data': json.loads(excel_result),
            'risk_assessment': json.loads(risk_result),
            'payment_proposal': json.loads(payment_proposal),
            'user_constraints': workflow_inputs['user_constraints'],
            'file_path': file_path
        }
        
        # Clean up uploaded file
        try:
            os.remove(file_path)
        except:
            pass
        
        logger.info(f"Treasury workflow completed for proposal {proposal_id}")
        
        return success_response({
            "proposal_id": proposal_id,
            "message": "Proposal generated successfully.",
            "next_step": f"GET /get_payment_proposal/{proposal_id}"
        })
        
    except Exception as e:
        logger.error(f"Error in submit_request: {str(e)}")
        return error_response(f"Internal server error: {str(e)}", 500)


@app.route('/get_payment_proposal/<proposal_id>', methods=['GET'])
def get_payment_proposal(proposal_id: str):
    """
    Retrieve payment proposal for human review.
    
    Returns structured payment proposal with risk assessment.
    """
    try:
        if proposal_id not in proposal_storage:
            return error_response("Proposal not found", 404)
        
        proposal_data = proposal_storage[proposal_id]
        
        if proposal_data['status'] != 'PENDING_PAYMENT_APPROVAL':
            return error_response(f"Invalid proposal status: {proposal_data['status']}")
        
        # Format response according to API contract
        response = {
            "proposal_id": proposal_id,
            "agent_analysis": {
                "excel_parsing_summary": proposal_data['excel_data']['metadata'],
                "risk_assessment_summary": proposal_data['risk_assessment']['risk_assessment'],
                "recommendations": proposal_data['risk_assessment']['recommendations']
            },
            "payment_proposals": proposal_data['payment_proposal']['individual_payments'],
            "risk_assessment": proposal_data['risk_assessment']
        }
        
        return success_response(response)
        
    except Exception as e:
        logger.error(f"Error in get_payment_proposal: {str(e)}")
        return error_response(f"Internal server error: {str(e)}", 500)


@app.route('/submit_payment_approval', methods=['POST'])
def submit_payment_approval():
    """
    Submit human decision on payment proposal.
    
    Executes approved payments and prepares for investment workflow.
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response("Missing JSON payload")
        
        proposal_id = data.get('proposal_id')
        approval_decision = data.get('approval_decision')  # approve_all, reject_all, partial
        approved_payments = data.get('approved_payments', [])
        comments = data.get('comments', '')
        
        if not proposal_id or approval_decision not in ['approve_all', 'reject_all', 'partial']:
            return error_response("Invalid approval decision or missing proposal_id")
        
        if proposal_id not in proposal_storage:
            return error_response("Proposal not found", 404)
        
        proposal_data = proposal_storage[proposal_id]
        
        # Process approval decision
        execution_result = {
            'proposal_id': proposal_id,
            'execution_status': 'SUCCESS',
            'timestamp': datetime.now().isoformat(),
            'approval_decision': approval_decision,
            'comments': comments,
            'executed_payments': [],
            'failed_payments': [],
            'total_executed_amount': 0.0,
            'remaining_balance': 0.0
        }
        
        # Simulate payment execution based on approval
        all_payments = proposal_data['payment_proposal']['individual_payments']
        
        if approval_decision == 'approve_all':
            execution_result['executed_payments'] = all_payments
            execution_result['total_executed_amount'] = sum(p['amount'] for p in all_payments)
        elif approval_decision == 'partial':
            # Filter payments by approved payment IDs
            executed = [p for p in all_payments if p['payment_id'] in approved_payments]
            failed = [p for p in all_payments if p['payment_id'] not in approved_payments]
            execution_result['executed_payments'] = executed
            execution_result['failed_payments'] = failed
            execution_result['total_executed_amount'] = sum(p['amount'] for p in executed)
            if failed:
                execution_result['execution_status'] = 'PARTIAL_SUCCESS'
        else:  # reject_all
            execution_result['failed_payments'] = all_payments
            execution_result['execution_status'] = 'FAILURE'
        
        # Calculate remaining balance for investment (simulated)
        # In real implementation, this would come from actual payment execution
        total_available = proposal_data['excel_data']['metadata']['total_records'] * 10000  # Simulated available funds
        execution_result['remaining_balance'] = total_available - execution_result['total_executed_amount']
        
        # Store execution result
        execution_storage[proposal_id] = execution_result
        
        # Update proposal status
        proposal_data['status'] = 'PAYMENT_EXECUTED'
        proposal_data['payment_execution'] = execution_result
        
        return success_response({
            "execution_status": execution_result['execution_status'],
            "message": f"Payment execution completed: {execution_result['execution_status']}",
            "next_step": f"GET /payment_execution_result/{proposal_id}"
        })
        
    except Exception as e:
        logger.error(f"Error in submit_payment_approval: {str(e)}")
        return error_response(f"Internal server error: {str(e)}", 500)


@app.route('/payment_execution_result/<proposal_id>', methods=['GET'])
def payment_execution_result(proposal_id: str):
    """
    Get detailed payment execution results.
    """
    try:
        if proposal_id not in execution_storage:
            return error_response("Execution result not found", 404)
        
        execution_result = execution_storage[proposal_id]
        
        return success_response({
            "proposal_id": proposal_id,
            "execution_status": execution_result['execution_status'],
            "executed_payments": execution_result['executed_payments'],
            "failed_payments": execution_result['failed_payments'],
            "total_executed_amount": execution_result['total_executed_amount'],
            "remaining_balance": execution_result['remaining_balance'],
            "timestamp": execution_result['timestamp']
        })
        
    except Exception as e:
        logger.error(f"Error in payment_execution_result: {str(e)}")
        return error_response(f"Internal server error: {str(e)}", 500)


@app.route('/get_investment_plan/<proposal_id>', methods=['GET'])
def get_investment_plan(proposal_id: str):
    """
    Generate and return investment plan for remaining funds after payment execution.
    """
    try:
        if proposal_id not in proposal_storage:
            return error_response("Proposal not found", 404)
        
        proposal_data = proposal_storage[proposal_id]
        
        if proposal_id not in execution_storage:
            return error_response("Payment execution not completed", 400)
        
        execution_result = execution_storage[proposal_id]
        remaining_balance = execution_result['remaining_balance']
        
        # Generate investment plan using Investment Analyzer Tool
        investment_analyzer = InvestmentAnalyzerTool()
        
        # Get user investment preferences from constraints
        user_constraints = proposal_data['user_constraints']
        investment_preferences = {
            'risk_tolerance': 'moderate',  # Default, could be configurable
            'emergency_reserve_percentage': 0.15,
            'minimum_emergency_reserve': 5000.0
        }
        
        # Generate investment plan
        investment_plan_result = investment_analyzer._run(
            available_funds=remaining_balance,
            user_investment_preferences=investment_preferences,
            payment_execution_result=json.dumps(execution_result)
        )
        
        investment_plan = json.loads(investment_plan_result)
        
        # Store investment plan
        proposal_data['investment_plan'] = investment_plan
        proposal_data['status'] = 'PENDING_INVESTMENT_APPROVAL'
        
        # Format response according to API contract
        allocations = []
        for recommendation in investment_plan.get('recommended_investments', []):
            allocations.append({
                'type': recommendation['investment_type'],
                'amount': recommendation['allocation'],
                'expected_yield': recommendation['expected_return'],
                'duration': recommendation.get('description', 'Variable'),
                'risk_level': recommendation['risk_level']
            })
        
        response = {
            "proposal_id": proposal_id,
            "remaining_balance": remaining_balance,
            "investment_plan": {
                "allocations": allocations,
                "summary": f"Diversified investment allocation across {len(allocations)} investment products"
            },
            "next_step": "POST /submit_investment_approval"
        }
        
        return success_response(response)
        
    except Exception as e:
        logger.error(f"Error in get_investment_plan: {str(e)}")
        return error_response(f"Internal server error: {str(e)}", 500)


@app.route('/submit_investment_approval', methods=['POST'])
def submit_investment_approval():
    """
    Submit human decision on investment plan.
    """
    try:
        data = request.get_json()
        
        if not data:
            return error_response("Missing JSON payload")
        
        proposal_id = data.get('proposal_id')
        approval_decision = data.get('approval_decision')  # approve, reject
        comments = data.get('comments', '')
        
        if not proposal_id or approval_decision not in ['approve', 'reject']:
            return error_response("Invalid approval decision or missing proposal_id")
        
        if proposal_id not in proposal_storage:
            return error_response("Proposal not found", 404)
        
        proposal_data = proposal_storage[proposal_id]
        
        # Process investment approval
        investment_execution = {
            'proposal_id': proposal_id,
            'execution_status': 'SUCCESS' if approval_decision == 'approve' else 'FAILURE',
            'timestamp': datetime.now().isoformat(),
            'approval_decision': approval_decision,
            'comments': comments,
            'executed_investments': [] if approval_decision == 'reject' else proposal_data['investment_plan']['recommended_investments']
        }
        
        # Store investment execution result
        proposal_data['investment_execution'] = investment_execution
        proposal_data['status'] = 'INVESTMENT_EXECUTED'
        
        return success_response({
            "execution_status": investment_execution['execution_status'],
            "message": f"Investment execution completed: {investment_execution['execution_status']}",
            "next_step": f"GET /investment_execution_result/{proposal_id}"
        })
        
    except Exception as e:
        logger.error(f"Error in submit_investment_approval: {str(e)}")
        return error_response(f"Internal server error: {str(e)}", 500)


@app.route('/investment_execution_result/<proposal_id>', methods=['GET'])
def investment_execution_result(proposal_id: str):
    """
    Get detailed investment execution results.
    """
    try:
        if proposal_id not in proposal_storage:
            return error_response("Proposal not found", 404)
        
        proposal_data = proposal_storage[proposal_id]
        
        if 'investment_execution' not in proposal_data:
            return error_response("Investment execution not completed", 400)
        
        investment_execution = proposal_data['investment_execution']
        
        return success_response({
            "proposal_id": proposal_id,
            "execution_status": investment_execution['execution_status'],
            "executed_investments": investment_execution['executed_investments'],
            "timestamp": investment_execution['timestamp']
        })
        
    except Exception as e:
        logger.error(f"Error in investment_execution_result: {str(e)}")
        return error_response(f"Internal server error: {str(e)}", 500)


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return error_response("Endpoint not found", 404)


@app.errorhandler(500)
def internal_error(error):
    return error_response("Internal server error", 500)


if __name__ == '__main__':
    logger.info("Starting Treasury Manager AI Agent API Server...")
    app.run(host='0.0.0.0', port=5001, debug=True)
