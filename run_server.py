#!/usr/bin/env python3
"""
Treasury Agent FastAPI Server Startup Script
"""
import os
import sys
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# Add the treasury_agent/src directory to the path so we can import the API server
sys.path.insert(0, str(Path(__file__).parent / "treasury_agent" / "src"))

def main():
    """Start the Treasury Agent FastAPI server"""
    
    # First, check if we have deployment environment variables
    # If not, load from .env file as fallback
    env_file_path = Path(__file__).parent / "treasury_agent" / ".env"
    
    # Check if essential deployment vars are missing
    deployment_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION_NAME", "MODEL"]
    missing_deployment_vars = [var for var in deployment_vars if not os.environ.get(var)]
    
    if missing_deployment_vars and env_file_path.exists():
        print(f"Loading environment variables from {env_file_path}")
        load_dotenv(env_file_path)
        print("✓ .env file loaded")
    elif missing_deployment_vars:
        print(f"WARNING: No deployment environment variables found and no .env file at {env_file_path}")
    else:
        print("Using deployment environment variables")
    
    # Set default environment variables if not provided
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5001"))
    
    print(f"Starting Treasury Agent Server on {host}:{port}")
    print("Environment variables:")
    print(f"  HOST: {host}")
    print(f"  PORT: {port}")
    
    # Verify required environment variables are now set
    missing_aws_vars = []
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        missing_aws_vars.append("AWS_ACCESS_KEY_ID")
    if not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        missing_aws_vars.append("AWS_SECRET_ACCESS_KEY")
    if not os.environ.get("AWS_REGION_NAME"):
        missing_aws_vars.append("AWS_REGION_NAME")
    
    if missing_aws_vars:
        print(f"ERROR: Missing AWS environment variables: {', '.join(missing_aws_vars)}")
        print("Please set them in deployment environment or in .env file")
    else:
        print("✓ AWS credentials configured")
    
    # Check model configuration
    model = os.environ.get("MODEL", "bedrock/us.amazon.nova-pro-v1:0")
    print(f"  MODEL: {model}")
    
    try:
        # Import and start the server
        uvicorn.run(
            "treasury_agent.api_server:app",
            host=host,
            port=port,
            reload=True,  # Enable auto-reload for development
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
