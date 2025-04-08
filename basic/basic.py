import requests
import time           # Added for timing
import psutil        # Added for CPU monitoring
import pynvml        # Added for GPU monitoring
import os            # Added for file path operations

OLLAMA_URL = "http://localhost:11434/api/generate"

# Added function to initialize GPU monitoring
def initialize_gpu():
    """Initialize GPU monitoring with pynvml."""
    try:
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count > 0:
            return pynvml.nvmlDeviceGetHandleByIndex(0)  # Use first GPU
        return None
    except pynvml.NVMLError:
        print("Warning: Could not initialize GPU monitoring (no NVIDIA GPU or driver found).")
        return None

# Added function to read GPU usage
def get_gpu_usage(handle):
    """Get GPU utilization percentage."""
    if handle is None:
        return "N/A"
    try:
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        return util.gpu  # GPU utilization as a percentage
    except pynvml.NVMLError:
        return "Error"

# Function to find Ollama PIDs and measure their CPU usage
def get_ollama_cpu_usage(interval=0.1):
    """Find ollama processes and return their combined CPU usage percentage."""
    ollama_processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        if 'ollama' in proc.info['name'].lower():
            try:
                ollama_processes.append(psutil.Process(proc.info['pid']))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue # Process might have terminated or access denied

    if not ollama_processes:
        print("Warning: Ollama process not found.")
        return "N/A"

    total_cpu_percent = 0
    # Measure CPU usage for each Ollama process
    for proc in ollama_processes:
        try:
            # Use interval to get usage over that period immediately following the request
            total_cpu_percent += proc.cpu_percent(interval=interval / len(ollama_processes))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue # Handle cases where process disappears during measurement

    # Cap the total CPU percent at the number of cores * 100
    # psutil returns total CPU percentage across all cores
    # Example: 4 cores could theoretically show 400%
    # total_cpu_percent = min(total_cpu_percent, psutil.cpu_count() * 100)
    # Note: cpu_percent usually returns a value <= 100 * cpu_count()
    # No explicit capping needed unless specific behavior desired.

    return total_cpu_percent

# Helper function to get Ollama process objects
def get_ollama_processes():
    """Finds and returns a list of psutil.Process objects for Ollama."""
    ollama_procs = []
    for proc in psutil.process_iter(['pid', 'name']):
        if 'ollama' in proc.info['name'].lower():
            try:
                # Get the full process object
                ollama_procs.append(psutil.Process(proc.info['pid']))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue # Process might have terminated or access denied
    return ollama_procs

# Modified query_model to measure CPU usage via cpu_times delta
def query_model(model_name, prompt):
    """Query the model and measure Ollama's average CPU usage during the request."""
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }

    ollama_procs = get_ollama_processes()
    if not ollama_procs:
        print("Warning: Ollama process not found before request.")
        # Decide how to handle - return error, default values?
        # For now, proceed but CPU usage will be N/A

    initial_cpu_times = {}
    for p in ollama_procs:
        try:
            initial_cpu_times[p.pid] = p.cpu_times()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"Warning: Could not get initial CPU times for PID {p.pid}")
            continue

    # Start timing *after* getting initial times
    start_time = time.time()

    # Original API call
    response = requests.post(OLLAMA_URL, json=payload)

    # Stop timing *before* getting final times
    end_time = time.time()
    elapsed_time = end_time - start_time

    final_cpu_times = {}
    # Refresh the process list in case PIDs changed (unlikely but possible)
    # Or just reuse ollama_procs if we assume PIDs are stable for the duration
    current_ollama_procs = {p.pid: p for p in get_ollama_processes()}

    total_cpu_time_delta = 0.0
    found_processes_after = 0

    for pid, initial_times in initial_cpu_times.items():
        if pid in current_ollama_procs:
            try:
                final_times = current_ollama_procs[pid].cpu_times()
                # Calculate delta for this process (user + system time)
                cpu_delta = (final_times.user - initial_times.user) + \
                            (final_times.system - initial_times.system)
                total_cpu_time_delta += cpu_delta
                found_processes_after += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"Warning: Could not get final CPU times for PID {pid}")
                continue
        else:
            print(f"Warning: Ollama process PID {pid} disappeared during request.")


    if not ollama_procs or found_processes_after == 0:
         # Handle case where no ollama processes were found or measured
         average_cpu_percent = "N/A"
    elif elapsed_time > 0:
        # Calculate average CPU percentage during the elapsed time
        # This percentage is relative to a single core.
        # A value > 100 means it used more than one core on average.
        average_cpu_percent = (total_cpu_time_delta / elapsed_time) * 100
    else:
        average_cpu_percent = 0.0 # Avoid division by zero if elapsed time is negligible

    result_data = {
        "ollama_avg_cpu_percent": average_cpu_percent, # New key name
        "elapsed_time": elapsed_time
    }

    if response.status_code == 200:
        result_data["response"] = response.json()["response"]
    else:
        result_data["response"] = f"Error: {response.status_code} - {response.text}"

    return result_data

if __name__ == "__main__":
    models = ["deepseek-coder:1.3b", "mistral", "llama2:13b"]
    
    # Added GPU initialization
    gpu_handle = initialize_gpu()
    
    ### general question answering
    # capital = "What is the capital of France?"
    python = "What are the 3 biggest breakthroughs in python programming in 2025?"

    # Determine the output file path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_md_file = os.path.join(script_dir, "basic_output.md")

    # Clear the output file at the start of the script run (optional)
    # with open(output_md_file, 'w', encoding='utf-8') as f:
    #     f.write("# Model Outputs and Performance\n\n")

    for model in models:
        print(f"\nModel: {model}")
        
        # Query model with resource tracking
        result = query_model(model, python)
        
        # Get GPU usage
        gpu_usage = get_gpu_usage(gpu_handle) if gpu_handle else "N/A"
        
        # Print response and resource usage (console output)
        print(f"Response: {result['response']}")
        # Updated CPU usage reporting
        if isinstance(result['ollama_avg_cpu_percent'], (int, float)):
            print(f"Ollama Avg CPU Usage During Request: {result['ollama_avg_cpu_percent']:.2f}%")
        else:
            print(f"Ollama Avg CPU Usage During Request: {result['ollama_avg_cpu_percent']}")
        print(f"GPU Usage: {gpu_usage}%")
        print(f"Time Taken: {result['elapsed_time']:.2f} seconds")
        print("-" * 50)

        # Write response and resource usage to Markdown file
        try:
            with open(output_md_file, 'a', encoding='utf-8') as f:
                f.write(f"## Model: {model}\n\n")
                f.write(f"**Prompt:**\n```\n{python}\n```\n\n") # Included the prompt
                f.write(f"**Response:**\n```\n{result['response']}\n```\n\n")
                f.write("**Performance:**\n")
                # Updated CPU usage reporting in file
                if isinstance(result['ollama_avg_cpu_percent'], (int, float)):
                    f.write(f"- Ollama Avg CPU Usage During Request: {result['ollama_avg_cpu_percent']:.2f}%\n")
                else:
                     f.write(f"- Ollama Avg CPU Usage During Request: {result['ollama_avg_cpu_percent']}\n")

                # Handle potential non-numeric GPU usage for formatting
                gpu_usage_str = f"{gpu_usage}%" if isinstance(gpu_usage, (int, float)) else str(gpu_usage)
                f.write(f"- GPU Usage: {gpu_usage_str}\n")
                f.write(f"- Time Taken: {result['elapsed_time']:.2f} seconds\n")
                f.write("\n---\n\n")
        except IOError as e:
            print(f"Error writing to file {output_md_file}: {e}")
    
    # Added GPU cleanup
    if gpu_handle:
        pynvml.nvmlShutdown()
