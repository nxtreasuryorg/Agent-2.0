#!/usr/bin/env python3
"""
Treasury Agent FastAPI Server Startup Script
"""
import os
import sys
import uvicorn
from pathlib import Path

# Add the src directory to the path so we can import the API server
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Start the Treasury Agent FastAPI server"""
    # Set default environment variables if not provided
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5001"))
    
    print(f"Starting Treasury Agent Server on {host}:{port}")
    print("Environment variables:")
    print(f"  HOST: {host}")
    print(f"  PORT: {port}")
    
    # Ensure required environment variables are set for AWS Bedrock
    missing_aws_vars = []
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        missing_aws_vars.append("AWS_ACCESS_KEY_ID")
    if not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        missing_aws_vars.append("AWS_SECRET_ACCESS_KEY")
    if not os.environ.get("AWS_REGION_NAME"):
        missing_aws_vars.append("AWS_REGION_NAME")
    
    if missing_aws_vars:
        print(f"WARNING: Missing AWS environment variables: {', '.join(missing_aws_vars)}")
        print("Please set them or check your .env file")
    
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
