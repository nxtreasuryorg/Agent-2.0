"""Payment Executor Tool for executing approved payments with USDT blockchain integration."""
from typing import Dict, Any, List, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import os
import sys

# Import configuration
from ..config.config_loader import get_config

# Import Web3 and crypto utilities for USDT transactions
try:
    from web3 import Web3
    from web3.exceptions import (TransactionNotFound, TimeExhausted, MismatchedABI, 
                               InvalidTransaction, BlockNotFound, InvalidAddress, ValidationError)
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

# Client and server will be deployed separately
# USDT utilities will be handled by the server's own web3 implementation
CLIENT_UTILS_AVAILABLE = False
client_utils = None

class PaymentExecutorInput(BaseModel):
    """Input schema for Payment Executor Tool."""
    proposal_id: str = Field(description="ID of the approved payment proposal")
    payment_details: Dict[str, Any] = Field(description="Payment details to execute")
    approval_status: str = Field(description="Approval status from HITL")

class PaymentExecutorTool(BaseTool):
    name: str = "Payment Executor Tool (SIMULATION MODE)"
    description: str = """
    USDT Payment Executor with Simulation Mode: Executes real USDT blockchain transactions in simulation mode.
    Uses integrated client-side USDT transaction logic for realistic payment processing.
    Simulation mode provides safe testing with real transaction validation without actual fund transfers.
    """
    args_schema: type[BaseModel] = PaymentExecutorInput
    
    def __init__(self, **kwargs):
        """Initialize with configuration from config file."""
        super().__init__(**kwargs)
        # Load configuration dynamically
        config = get_config()
        self._config = {
            'processing_fee_rate': config.get_processing_fee_rate(),
            'simulation_mode': config.is_simulation_mode(),
            'default_currency': config.get_default_currency(),
            'client_available': CLIENT_UTILS_AVAILABLE and WEB3_AVAILABLE
        }
        
        if not self._config['client_available']:
            print("WARNING: Client USDT utilities not available")

    @property
    def processing_fee_rate(self) -> float:
        return self._config['processing_fee_rate']
    
    @property
    def simulation_mode(self) -> bool:
        return self._config['simulation_mode']
    
    @property
    def client_available(self) -> bool:
        return self._config['client_available']
    
    @property
    def default_currency(self) -> str:
        return self._config['default_currency']

    def _check_balance_usdt(self, wallet_pubkey: str) -> float:
        """Check USDT balance using client utilities."""
        if not self.client_available:
            raise RuntimeError("Client USDT utilities not available")
        
        try:
            balance = client_utils.get_account_usdt_balance(wallet_pubkey)
            return balance if balance >= 0 else 0.0
        except Exception as e:
            print(f"Error checking USDT balance: {e}")
            raise

    def _execute_usdt_transfer(self, sender_pubkey: str, recipient_pubkey: str, amount: float) -> Dict[str, Any]:
        """Execute USDT transfer using client utilities in simulation mode."""
        if not self.client_available:
            raise RuntimeError("Client USDT utilities not available")
        
        try:
            if self.simulation_mode:
                # Perform all validation checks but don't actually execute
                print(f"[SIMULATION] Validating USDT transfer: {amount} from {sender_pubkey} to {recipient_pubkey}")
                
                # Check if addresses are valid
                if not Web3.is_address(sender_pubkey) or not Web3.is_address(recipient_pubkey):
                    return {
                        "status": "failed",
                        "error": "Invalid wallet address",
                        "simulation_note": "Address validation failed in simulation"
                    }
                
                # Check balance
                balance = self._check_balance_usdt(sender_pubkey)
                if balance < amount:
                    return {
                        "status": "failed", 
                        "error": f"Insufficient balance. Available: {balance}, Required: {amount}",
                        "simulation_note": "Balance check failed in simulation"
                    }
                
                # Simulate successful transaction
                return {
                    "status": "success",
                    "transaction_hash": f"SIM-{uuid.uuid4().hex[:16]}",
                    "confirmation_code": f"SIM-{uuid.uuid4().hex[:8]}",
                    "simulation_note": "SIMULATION - Transaction validated but not executed"
                }
            else:
                # Real execution (disabled for safety)
                print("WARNING: Real execution mode detected but blocked for safety")
                return {
                    "status": "blocked",
                    "error": "Real execution blocked for safety",
                    "simulation_note": "Real execution intentionally disabled"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "simulation_note": f"Error during transaction simulation: {type(e).__name__}"
            }

    def _run(self, proposal_id: str, payment_details: Dict[str, Any], 
             approval_status: str) -> Dict[str, Any]:
        """Execute USDT payments using integrated client logic in simulation mode."""
        try:
            print(f"[SIMULATION MODE] Processing USDT payment proposal: {proposal_id}")
            print(f"[CLIENT INTEGRATION] Using client USDT utilities: {self.client_available}")
            
            if approval_status != "approved":
                return {
                    "success": False,
                    "proposal_id": proposal_id,
                    "status": "rejected",
                    "message": "Payment proposal was not approved",
                    "timestamp": datetime.now().isoformat()
                }
            
            execution_result = {
                "proposal_id": proposal_id,
                "execution_id": f"EXEC-{uuid.uuid4().hex[:8]}",
                "status": "processing",
                "timestamp": datetime.now().isoformat(),
                "payments_processed": [],
                "summary": {},
                "client_integration": self.client_available,
                "simulation_mode": self.simulation_mode
            }
            
            total_success = 0
            total_failed = 0
            total_amount_processed = 0
            
            # Get custody wallet from payment details
            custody_wallet = payment_details.get("custody_wallet")
            if not custody_wallet:
                return {
                    "success": False,
                    "error": "Custody wallet not specified in payment details",
                    "proposal_id": proposal_id,
                    "status": "error"
                }
            
            # Check initial balance
            initial_balance = self._check_balance_usdt(custody_wallet)
            print(f"[SIMULATION] Initial USDT balance: {initial_balance}")
            
            # Process each payment using integrated USDT logic
            for payment in payment_details.get("payments", []):
                transaction_id = f"TXN-{uuid.uuid4().hex[:12]}"
                recipient = payment.get("recipient_wallet") or payment.get("recipient")
                amount = float(payment.get("amount", 0))
                
                print(f"[SIMULATION] Processing USDT payment: {amount} USDT to {recipient}")
                
                # Execute USDT transfer using client utilities
                transfer_result = self._execute_usdt_transfer(
                    sender_pubkey=custody_wallet,
                    recipient_pubkey=recipient, 
                    amount=amount
                )
                
                payment_result = {
                    "transaction_id": transaction_id,
                    "recipient": recipient,
                    "amount": amount,
                    "currency": self.default_currency,
                    "reference": payment.get("reference", ""),
                    "purpose": payment.get("purpose", ""),
                    "status": transfer_result["status"],
                    "processed_at": datetime.now().isoformat(),
                    "processing_fee": amount * self.processing_fee_rate,
                    "transaction_hash": transfer_result.get("transaction_hash"),
                    "confirmation_code": transfer_result.get("confirmation_code"),
                    "simulation_note": transfer_result.get("simulation_note", "USDT transaction simulation")
                }
                
                # Add error details if failed
                if transfer_result["status"] != "success":
                    payment_result["error"] = transfer_result.get("error", "Unknown error")
                
                # Track results
                if payment_result["status"] == "success":
                    total_success += 1
                    total_amount_processed += amount
                else:
                    total_failed += 1
                
                execution_result["payments_processed"].append(payment_result)
            
            # Calculate totals
            total_fees = total_amount_processed * self.processing_fee_rate
            remaining_balance = initial_balance - total_amount_processed - total_fees
            
            # Update execution summary
            execution_result["summary"] = {
                "total_payments": len(payment_details.get("payments", [])),
                "successful": total_success,
                "failed": total_failed,
                "total_amount_processed": total_amount_processed,
                "processing_fees": total_fees,
                "net_amount": total_amount_processed - total_fees
            }
            
            execution_result["balance_info"] = {
                "initial_balance": initial_balance,
                "total_debited": total_amount_processed + total_fees,
                "remaining_balance": max(0, remaining_balance)
            }
            
            # Set final status
            if total_failed == 0:
                execution_result["status"] = "simulation_completed"
                execution_result["message"] = f"[SIMULATION] All {total_success} USDT payments validated successfully"
            elif total_success > 0:
                execution_result["status"] = "simulation_partial_success"
                execution_result["message"] = f"[SIMULATION] {total_success} payments succeeded, {total_failed} failed"
            else:
                execution_result["status"] = "simulation_failed"
                execution_result["message"] = "[SIMULATION] All payment validations failed"
            
            execution_result["success"] = True
            execution_result["completed_at"] = datetime.now().isoformat()
            execution_result["disclaimer"] = "SIMULATION MODE - No actual USDT transfers were executed"
            
            return execution_result
            
        except Exception as e:
            return {
                "error": str(e),
                "success": False,
                "proposal_id": proposal_id,
                "status": "error",
                "simulation_mode": self.simulation_mode,
                "metadata": {"error_type": type(e).__name__}
            }
