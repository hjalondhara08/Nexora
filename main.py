import os
import sys
import subprocess

def find_python_executable():
    """Locates the project virtual environment Python if available."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(current_dir, ".venv", "bin", "python")
    if os.path.isfile(venv_python) and os.access(venv_python, os.X_OK):
        return venv_python
    venv_python_win = os.path.join(current_dir, ".venv", "Scripts", "python.exe")
    if os.path.isfile(venv_python_win):
        return venv_python_win
    return sys.executable

def main():
    print("=" * 60)
    print("🚀 Nexora — Production Hybrid RAG & Multi-Tool Agentic Platform")
    print("=" * 60)
    print("\nStarting Streamlit Frontend interface...\n")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(current_dir, "src", "nexora", "ui", "app.py")
    if not os.path.exists(app_path):
        app_path = os.path.join(current_dir, "frontend.py")
        
    py_exec = find_python_executable()
    print(f"Using Python runtime: {py_exec}\n")
    
    cmd = [py_exec, "-m", "streamlit", "run", app_path, *sys.argv[1:]]
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
