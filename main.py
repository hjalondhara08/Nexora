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

    current_dir = os.path.dirname(os.path.abspath(__file__))
    py_exec = find_python_executable()

    # Legacy Streamlit flag if user explicitly requests running archived Streamlit
    if "--streamlit" in sys.argv:
        print("\nStarting Archived Streamlit Frontend interface...\n")
        archive_app_path = os.path.join(current_dir, "archive", "ui", "app.py")
        cmd = [py_exec, "-m", "streamlit", "run", archive_app_path]
        subprocess.run(cmd)
        return

    print("\nStarting Async FastAPI Backend & React Frontend Server...\n")
    print(f"Using Python runtime: {py_exec}")
    print("FastAPI Backend: http://0.0.0.0:8000")
    print("API Documentation: http://0.0.0.0:8000/docs")
    print("React Web UI: http://0.0.0.0:8000/\n")

    # Ensure src is in PYTHONPATH
    src_dir = os.path.join(current_dir, "src")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"

    cmd = [
        py_exec,
        "-m",
        "uvicorn",
        "nexora.api.server:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ]
    subprocess.run(cmd, env=env)

if __name__ == "__main__":
    main()
