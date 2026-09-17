import sys
import subprocess
import os

def main():
    print("=" * 60)
    print("🚀 Nexora — Production Hybrid RAG & Multi-Tool Agentic Platform")
    print("=" * 60)
    print("\nStarting Streamlit Frontend interface...\n")
    subprocess.run(["streamlit", "run", "frontend.py"])

if __name__ == "__main__":
    main()
