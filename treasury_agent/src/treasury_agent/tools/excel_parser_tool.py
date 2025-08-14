from crewai.tools import BaseTool
from typing import Type, Dict, Any, List
from pydantic import BaseModel, Field
import pandas as pd
import openpyxl
import json
from pathlib import Path
import logging


class ExcelParserInput(BaseModel):
    """Input schema for ExcelParserTool."""
    file_path: str = Field(..., description="Path to the Excel file to parse")
    user_constraints: Dict[str, Any] = Field(
        default={}, 
        description="User-defined constraints including minimum balance, transaction limits, special conditions"
    )


class ExcelParserTool(BaseTool):
    name: str = "Excel Parser and Normalizer"
    description: str = (
        "Handles unpredictable Excel file uploads, extracts financial data, and standardizes it for analysis. "
        "Supports various Excel formats, detects sheets/headers dynamically, normalizes columns, handles merged cells "
        "and empty rows, and outputs structured JSON with data quality indicators."
    )
    args_schema: Type[BaseModel] = ExcelParserInput

    def _run(self, file_path: str, user_constraints: Dict[str, Any] = None) -> str:
        """
        Parse and normalize Excel file containing financial data.
        
        Args:
            file_path: Path to the Excel file
            user_constraints: User-defined financial constraints
            
        Returns:
            JSON string containing normalized financial data with metadata
        """
        try:
            if user_constraints is None:
                user_constraints = {}
                
            # Initialize result structure
            result = {
                "success": True,
                "normalized_data": [],
                "metadata": {
                    "file_path": file_path,
                    "sheets_processed": [],
                    "total_records": 0,
                    "data_quality": {
                        "valid_records": 0,
                        "invalid_records": 0,
                        "warnings": []
                    }
                },
                "user_constraints": user_constraints,
                "parsing_logs": []
            }
            
            # Load Excel file and detect sheets
            excel_file = pd.ExcelFile(file_path)
            result["parsing_logs"].append(f"Loaded Excel file with {len(excel_file.sheet_names)} sheets")
            
            all_financial_data = []
            
            # Process each sheet
            for sheet_name in excel_file.sheet_names:
                try:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    result["metadata"]["sheets_processed"].append(sheet_name)
                    result["parsing_logs"].append(f"Processing sheet: {sheet_name}")
                    
                    # Auto-detect financial columns
                    financial_data = self._extract_financial_data(df, sheet_name)
                    all_financial_data.extend(financial_data)
                    
                except Exception as e:
                    result["parsing_logs"].append(f"Warning: Could not process sheet {sheet_name}: {str(e)}")
                    result["metadata"]["data_quality"]["warnings"].append(f"Sheet {sheet_name} processing failed: {str(e)}")
            
            # Normalize and validate data
            result["normalized_data"] = self._normalize_financial_data(all_financial_data)
            result["metadata"]["total_records"] = len(result["normalized_data"])
            
            # Data quality assessment
            valid_records = 0
            invalid_records = 0
            
            for record in result["normalized_data"]:
                if self._validate_record(record, user_constraints):
                    valid_records += 1
                else:
                    invalid_records += 1
            
            result["metadata"]["data_quality"]["valid_records"] = valid_records
            result["metadata"]["data_quality"]["invalid_records"] = invalid_records
            
            result["parsing_logs"].append(f"Parsing completed: {valid_records} valid, {invalid_records} invalid records")
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "parsing_logs": [f"Excel parsing failed: {str(e)}"]
            }
            return json.dumps(error_result, indent=2)
    
    def _extract_financial_data(self, df: pd.DataFrame, sheet_name: str) -> List[Dict[str, Any]]:
        """Extract financial data from DataFrame by detecting common financial columns."""
        financial_data = []
        
        # Common column mappings (case-insensitive)
        column_mappings = {
            'amount': ['amount', 'value', 'sum', 'total', 'payment', 'balance'],
            'description': ['description', 'details', 'memo', 'reference', 'note'],
            'date': ['date', 'transaction_date', 'payment_date', 'due_date'],
            'account': ['account', 'account_number', 'from_account', 'to_account'],
            'recipient': ['recipient', 'payee', 'vendor', 'supplier', 'beneficiary'],
            'currency': ['currency', 'curr', 'ccy'],
            'category': ['category', 'type', 'classification']
        }
        
        # Auto-detect columns
        detected_columns = {}
        for col in df.columns:
            col_lower = str(col).lower().strip()
            for standard_name, variations in column_mappings.items():
                if any(variation in col_lower for variation in variations):
                    detected_columns[standard_name] = col
                    break
        
        # Process each row
        for index, row in df.iterrows():
            try:
                record = {
                    "sheet_name": sheet_name,
                    "row_number": index + 2,  # Excel row number (accounting for header)
                    "amount": None,
                    "description": "",
                    "date": None,
                    "account": "",
                    "recipient": "",
                    "currency": "USD",  # Default
                    "category": "",
                    "raw_data": {}
                }
                
                # Extract data based on detected columns
                for standard_name, excel_col in detected_columns.items():
                    value = row.get(excel_col)
                    if pd.notna(value):
                        record[standard_name] = str(value).strip()
                
                # Store raw data for reference
                record["raw_data"] = {str(k): str(v) for k, v in row.items() if pd.notna(v)}
                
                # Only include rows with amount data
                if record["amount"] and record["amount"] != "":
                    financial_data.append(record)
                    
            except Exception as e:
                logging.warning(f"Could not process row {index} in sheet {sheet_name}: {e}")
        
        return financial_data
    
    def _normalize_financial_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize financial data for consistency."""
        normalized_data = []
        
        for record in raw_data:
            try:
                normalized_record = record.copy()
                
                # Normalize amount
                if record.get("amount"):
                    amount_str = str(record["amount"]).replace(",", "").replace("$", "").strip()
                    try:
                        normalized_record["amount"] = float(amount_str)
                    except:
                        normalized_record["amount"] = 0.0
                        normalized_record["validation_errors"] = normalized_record.get("validation_errors", [])
                        normalized_record["validation_errors"].append("Invalid amount format")
                
                # Normalize date
                if record.get("date"):
                    try:
                        date_value = pd.to_datetime(record["date"])
                        normalized_record["date"] = date_value.isoformat()
                    except:
                        normalized_record["date"] = None
                        normalized_record["validation_errors"] = normalized_record.get("validation_errors", [])
                        normalized_record["validation_errors"].append("Invalid date format")
                
                # Set defaults for missing required fields
                if not normalized_record.get("currency"):
                    normalized_record["currency"] = "USD"
                
                if not normalized_record.get("description"):
                    normalized_record["description"] = "No description provided"
                
                normalized_data.append(normalized_record)
                
            except Exception as e:
                logging.warning(f"Could not normalize record: {e}")
        
        return normalized_data
    
    def _validate_record(self, record: Dict[str, Any], user_constraints: Dict[str, Any]) -> bool:
        """Validate financial record against user constraints and business rules."""
        try:
            # Basic validations
            if not record.get("amount") or record["amount"] <= 0:
                return False
            
            # User constraint validations
            min_balance = user_constraints.get("minimum_balance", 0)
            if record["amount"] < min_balance:
                record["validation_errors"] = record.get("validation_errors", [])
                record["validation_errors"].append(f"Amount below minimum balance requirement: {min_balance}")
                return False
            
            max_transaction = user_constraints.get("transaction_limit")
            if max_transaction and record["amount"] > max_transaction:
                record["validation_errors"] = record.get("validation_errors", [])
                record["validation_errors"].append(f"Amount exceeds transaction limit: {max_transaction}")
                return False
            
            return True
            
        except Exception as e:
            logging.warning(f"Validation error for record: {e}")
            return False
