"""
Run script for Dementia Chatbot
Simple launcher for the Streamlit application
"""
import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

def main():
    """Main function to run the Dementia Chatbot"""
    load_dotenv(Path(".env"))
    print("🧠 Starting Dementia Chatbot...")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("main.py").exists():
        print("❌ Error: main.py not found. Please run this from the project root directory.")
        sys.exit(1)
    
    # Check if requirements are installed
    try:
        import streamlit
        import whisper
        import sentence_transformers
        print("✅ Core dependencies found")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install requirements: pip install -r requirements.txt")
        sys.exit(1)
    
    # Check if Gemini API key is set
    if os.getenv("GEMINI_API_KEY"):
        print("✅ Gemini API key detected")
    else:
        print("⚠️  Warning: GEMINI_API_KEY is not set. LLM answers will use fallback mode.")
    
    print("=" * 50)
    print("🚀 Launching Streamlit application...")
    print("The application will open in your default web browser.")
    print("Press Ctrl+C to stop the application.")
    print("=" * 50)
    
    # Run Streamlit
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "main.py",
            "--server.port", "8501",
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false"
        ])
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Error running application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
