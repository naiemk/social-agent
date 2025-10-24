"""
Setup script for the social media agent.

This script provides easy setup and configuration for the social media agent.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 9):
        print("Error: Python 3.9 or higher is required")
        sys.exit(1)
    print(f"✓ Python version {sys.version_info.major}.{sys.version_info.minor} is compatible")


def install_dependencies():
    """Install required dependencies using uv."""
    print("Installing dependencies...")
    try:
        subprocess.run(["uv", "sync"], check=True, capture_output=True, text=True)
        print("✓ Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        print("Please ensure uv is installed and try again")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: uv is not installed. Please install uv first:")
        print("curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)


def setup_environment():
    """Set up environment configuration."""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("✓ .env file already exists")
        return
    
    if not env_example.exists():
        print("Error: .env.example file not found")
        sys.exit(1)
    
    # Copy example to .env
    env_example.rename(env_file)
    print("✓ Created .env file from template")
    print("⚠️  Please edit .env file with your actual configuration values")


def validate_configuration():
    """Validate the configuration."""
    try:
        from config import validate_required_credentials
        validate_required_credentials()
        print("✓ Configuration validation passed")
    except ValueError as e:
        print(f"⚠️  Configuration validation failed: {e}")
        print("Please check your .env file and ensure all required values are set")


def create_directories():
    """Create necessary directories."""
    directories = ["logs", "data"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    print("✓ Created necessary directories")


def main():
    """Main setup function."""
    print("Setting up Social Media Agent...")
    print("=" * 50)
    
    check_python_version()
    install_dependencies()
    create_directories()
    setup_environment()
    validate_configuration()
    
    print("=" * 50)
    print("Setup complete!")
    print("\nNext steps:")
    print("1. Edit .env file with your API credentials")
    print("2. Run the agent once: python -m social_media_agent")
    print("3. Run the agent on schedule: python -m social_media_agent --schedule")
    print("\nFor more information, see README.md")


if __name__ == "__main__":
    main()
