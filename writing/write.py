import requests
import time
import psutil
import pynvml
import os

OLLAMA_URL = "http://localhost:11434/api/generate"

def initialize_gpu():
    """Initialize GPU monitoring with pynvml."""
    try:
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count > 0:
            return pynvml.nvmlDeviceGetHandleByIndex(0)
        return None
    except pynvml.NVMLError:
        print("Warning: Could not initialize GPU monitoring (no NVIDIA GPU or driver found).")
        return None

def get_gpu_usage(handle):
    """Get GPU utilization percentage."""
    if handle is None: return "N/A"
    try:
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        return util.gpu
    except pynvml.NVMLError: return "Error"

def get_ollama_processes():
    """Finds and returns a list of psutil.Process objects for Ollama."""
    ollama_procs = []
    for proc in psutil.process_iter(['pid', 'name']):
        proc_name = proc.info.get('name')
        if proc_name and 'ollama' in proc_name.lower():
            try:
                ollama_procs.append(psutil.Process(proc.info['pid']))
            except (psutil.NoSuchProcess, psutil.AccessDenied): continue
    return ollama_procs

def get_ollama_memory_usage():
    """Calculates the total RSS memory usage (in MB) of all Ollama processes."""
    total_rss = 0
    ollama_procs = get_ollama_processes()
    if not ollama_procs:
        print("Warning: Ollama process not found during memory measurement.")
        return "N/A"
    for p in ollama_procs:
        try:
            total_rss += p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"Warning: Could not get memory info for PID {p.pid}")
            continue
    return total_rss / (1024 * 1024) if isinstance(total_rss, (int, float)) else "Error"

def query_model(model_name, prompt):
    """Queries the model and measures performance metrics."""
    payload = {"model": model_name, "prompt": prompt, "stream": False}

    ollama_procs_before = get_ollama_processes()
    initial_cpu_times = {}
    if not ollama_procs_before:
        print("Warning: Ollama process not found before request.")
    for p in ollama_procs_before:
        try:
            initial_cpu_times[p.pid] = p.cpu_times()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"Warning: Could not get initial CPU times for PID {p.pid}")
            continue

    start_time = time.time()
    response = requests.post(OLLAMA_URL, json=payload)
    end_time = time.time()
    elapsed_time = end_time - start_time

    total_cpu_time_delta = 0.0
    measured_pids_after = 0
    current_ollama_procs = {p.pid: p for p in get_ollama_processes()}
    for pid, initial_times in initial_cpu_times.items():
        if pid in current_ollama_procs:
            try:
                final_times = current_ollama_procs[pid].cpu_times()
                cpu_delta = (final_times.user - initial_times.user) + \
                            (final_times.system - initial_times.system)
                total_cpu_time_delta += max(0, cpu_delta)
                measured_pids_after += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"Warning: Could not get final CPU times for PID {pid}")
                continue
        else: print(f"Warning: Ollama process PID {pid} disappeared during request.")

    if measured_pids_after == 0:
        average_cpu_percent = "N/A"
        print("Warning: No Ollama processes could be measured for CPU after the request.")
    elif elapsed_time > 0:
        average_cpu_percent = (total_cpu_time_delta / elapsed_time) * 100
    else: average_cpu_percent = float('inf') if total_cpu_time_delta > 0 else 0.0

    ollama_rss_mb = get_ollama_memory_usage()

    result_data = {
        "ollama_avg_cpu_percent": average_cpu_percent,
        "ollama_rss_mb": ollama_rss_mb,
        "elapsed_time": elapsed_time
    }
    if response.status_code == 200:
        result_data["response"] = response.json()["response"]
    else: result_data["response"] = f"Error: {response.status_code} - {response.text}"

    return result_data

if __name__ == "__main__":
    models = ["deepseek-coder:1.3b", "mistral", "llama2:13b"]
    prompts = [
        "Write a short story about a grumpy dwarf",
        "Write a short story about an SMU student studying large language models",
        "Write a short story about a large language model who gains sentience",
    ]

    gpu_handle = initialize_gpu()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_md_file = os.path.join(script_dir, "write_output.md")

    try:
        with open(output_md_file, 'w', encoding='utf-8') as f:
            f.write("# Model Outputs and Performance\n\n")
            f.write(f"*Execution started: {time.strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
    except IOError as e: print(f"Error clearing file {output_md_file}: {e}")

    for model in models:
        print(f"\n===== Testing Model: {model} =====")

        for i, prompt in enumerate(prompts):
            print(f"\n--- Prompt {i+1}/{len(prompts)} for {model} ---")
            print(f"Prompt: {prompt}")

            result = query_model(model, prompt)
            gpu_usage = get_gpu_usage(gpu_handle) if gpu_handle else "N/A"

            print(f"Response: {result['response']}")
            cpu_usage_val = result['ollama_avg_cpu_percent']
            ram_usage_val = result['ollama_rss_mb']

            if isinstance(cpu_usage_val, (int, float)): print(f"Ollama Avg CPU Usage: {cpu_usage_val:.2f}%")
            else: print(f"Ollama Avg CPU Usage: {cpu_usage_val}")

            if isinstance(ram_usage_val, (int, float)): print(f"Ollama RAM Usage (RSS): {ram_usage_val:.2f} MB")
            else: print(f"Ollama RAM Usage (RSS): {ram_usage_val}")

            if isinstance(gpu_usage, (int, float)): print(f"GPU Usage: {gpu_usage:.2f}%")
            else: print(f"GPU Usage: {gpu_usage}")

            print(f"Time Taken: {result['elapsed_time']:.2f} seconds")
            print("-" * 30) 

            try:
                with open(output_md_file, 'a', encoding='utf-8') as f:
                    f.write(f"## Model: {model}\n\n")
                    f.write(f"**Prompt {i+1}/{len(prompts)}:**\n") 
                    f.write(f"```\n{prompt}\n```\n\n")
                    f.write(f"**Response:**\n```\n{result['response']}\n```\n\n")
                    f.write("**Performance:**\n")
                    if isinstance(cpu_usage_val, (int, float)): f.write(f"- Ollama Avg CPU Usage: {cpu_usage_val:.2f}%\n")
                    else: f.write(f"- Ollama Avg CPU Usage: {cpu_usage_val}\n")
                    if isinstance(ram_usage_val, (int, float)): f.write(f"- Ollama RAM Usage (RSS): {ram_usage_val:.2f} MB\n")
                    else: f.write(f"- Ollama RAM Usage (RSS): {ram_usage_val}\n")
                    gpu_usage_str = f"{gpu_usage:.2f}%" if isinstance(gpu_usage, (int, float)) else str(gpu_usage)
                    f.write(f"- GPU Usage: {gpu_usage_str}\n")
                    f.write(f"- Time Taken: {result['elapsed_time']:.2f} seconds\n")
                    f.write("\n---\n\n")
            except IOError as e: print(f"Error writing to file {output_md_file}: {e}")

          

    if gpu_handle:
        try: pynvml.nvmlShutdown()
        except pynvml.NVMLError as e: print(f"Error shutting down NVML: {e}")

    print("\n===== Script Finished =====")
