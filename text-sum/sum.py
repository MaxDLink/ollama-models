import requests
import time
import psutil
import pynvml
import os
import PyPDF2  # Added for PDF reading

OLLAMA_URL = "http://localhost:11434/api/generate"

# --- GPU Functions ---
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

# --- PDF Extraction Function ---
def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted:  # Ensure text was actually extracted
                    text += extracted + "\n" # Use escaped newline for consistency
            # Basic cleanup: replace multiple newlines/spaces, strip leading/trailing whitespace
            text = ' '.join(text.split())
            return text
    except FileNotFoundError:
        return f"Error: PDF file not found at {pdf_path}"
    except Exception as e:
        return f"Error reading PDF {os.path.basename(pdf_path)}: {str(e)}"

# --- Ollama Process Functions ---
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

# --- Core Query Function ---
def query_model(model_name, prompt):
    """Queries the model and measures performance metrics."""
    payload = {"model": model_name, "prompt": prompt, "stream": False}

    # --- CPU Measurement Setup ---
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

    # --- Execute Request and Time ---
    start_time = time.time()
    response = requests.post(OLLAMA_URL, json=payload)
    end_time = time.time()
    elapsed_time = end_time - start_time

    # --- CPU Measurement Calculation ---
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

    # --- Memory Measurement ---
    ollama_rss_mb = get_ollama_memory_usage()

    # --- Prepare Result ---
    result_data = {
        "ollama_avg_cpu_percent": average_cpu_percent,
        "ollama_rss_mb": ollama_rss_mb,
        "elapsed_time": elapsed_time
    }
    if response.status_code == 200:
        result_data["response"] = response.json()["response"]
    else: result_data["response"] = f"Error: {response.status_code} - {response.text}"

    return result_data

# --- Main Execution Block ---
if __name__ == "__main__":
    models = ["deepseek-coder:1.3b", "mistral", "llama2:13b"]
    # --- Define the PDF path ---
    pdf_path = "./pyCrashCourse.pdf" # path to pdf

    # --- Define your list of summarization prompts ---
    summarization_prompt_templates = [
        "Provide a concise summary of the following text:",
        "How would you rate this text from an educational standpoint?",
        "What is the main topic discussed in the following text?",
        "Summarize the following content in bullet points:",
    ]
    # -----------------------------------------

    # --- Extract PDF Text ---
    print(f"Attempting to read PDF: {pdf_path}")
    pdf_text = extract_text_from_pdf(pdf_path)
    pdf_basename = os.path.basename(pdf_path) # Get filename for prompts/output

    if pdf_text.startswith("Error"):
        print(pdf_text)
        exit(1) # Exit if PDF cannot be read
    else:
        # Limit text length to avoid overly long prompts (adjust as needed)
        max_chars = 4000
        if len(pdf_text) > max_chars:
            print(f"PDF text truncated to first {max_chars} characters for prompts.")
            truncated_pdf_text = pdf_text[:max_chars]
        else:
            truncated_pdf_text = pdf_text
        print(f"Successfully read and processed PDF: {pdf_basename}")

    gpu_handle = initialize_gpu()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_md_file = os.path.join(script_dir, "sum_output.md") # .md file to save output

    # Open file and write header
    try:
        with open(output_md_file, 'w', encoding='utf-8') as f:
            f.write(f"""# PDF Summarization and Performance: {pdf_basename}

""")
            f.write(f"""*Execution started: {time.strftime('%Y-%m-%d %H:%M:%S')}*
""")
            f.write(f"""*Source PDF: {pdf_path}*

""")
            if len(pdf_text) > max_chars:
                 f.write(f"""*Note: PDF text used in prompts was truncated to the first {max_chars} characters.*

""")
    except IOError as e:
        print(f"Error preparing output file {output_md_file}: {e}")
        if gpu_handle:
            try: pynvml.nvmlShutdown()
            except pynvml.NVMLError as nv_err: print(f"Error shutting down NVML: {nv_err}")
        exit(1) # Exit if we can't write the header

    # --- Main Processing Loop (Models and Prompts) ---
    try:
        with open(output_md_file, 'a', encoding='utf-8') as f:
            for model in models:
                print(f"\n===== Testing Model: {model} for PDF: {pdf_basename} =====")

                for i, prompt_template in enumerate(summarization_prompt_templates):
                    # Construct the final prompt
                    final_prompt = f"{prompt_template}\n\n---\n\n{truncated_pdf_text}\n\n---"

                    print(f"\n--- Task {i+1}/{len(summarization_prompt_templates)} for {model} ---")
                    print(f"Prompt Base: {prompt_template}")

                    # Query the model
                    result = query_model(model, final_prompt)
                    gpu_usage = get_gpu_usage(gpu_handle) if gpu_handle else "N/A"

                    # Console Output Snippet
                    response_snippet = result['response'].split('\n')[0] # First line
                    if len(result['response']) > 100: response_snippet += "..."
                    print(f"Response Snippet: {response_snippet}")

                    # --- Write results to Markdown File ---
                    cpu_usage_val = result['ollama_avg_cpu_percent']
                    ram_usage_val = result['ollama_rss_mb']
                    elapsed_time_val = result['elapsed_time']

                    f.write(f"## Model: {model}\n\n")
                    f.write(f"**Task {i+1}/{len(summarization_prompt_templates)} (Source: {pdf_basename}):**\n")
                    f.write(f"**Prompt Template:**\n```\n{prompt_template}\n```\n\n")
                    f.write(f"**Response:**\n```\n{result['response']}\n```\n\n")
                    f.write("**Performance:**\n")

                    # Format and write performance metrics
                    if isinstance(cpu_usage_val, (int, float)):
                        f.write(f"- Ollama Avg CPU Usage: {cpu_usage_val:.2f}%\n")
                    else:
                        f.write(f"- Ollama Avg CPU Usage: {cpu_usage_val}\n")

                    if isinstance(ram_usage_val, (int, float)):
                        f.write(f"- Ollama RAM Usage (RSS): {ram_usage_val:.2f} MB\n")
                    else:
                        f.write(f"- Ollama RAM Usage (RSS): {ram_usage_val}\n")

                    gpu_usage_str = f"{gpu_usage:.2f}%" if isinstance(gpu_usage, (int, float)) else str(gpu_usage)
                    f.write(f"- GPU Usage: {gpu_usage_str}\n")

                    f.write(f"- Time Taken: {elapsed_time_val:.2f} seconds\n")
                    f.write("\n---\n\n") # Separator

    except IOError as e:
        print(f"Error writing results to file {output_md_file}: {e}")
    except Exception as e: # Catch other potential errors during processing
        print(f"An unexpected error occurred during processing: {e}")
    finally:
        # --- Cleanup --- Ensure GPU resources are released
        if gpu_handle:
            try:
                pynvml.nvmlShutdown()
                print("NVML shut down successfully.")
            except pynvml.NVMLError as e:
                print(f"Error shutting down NVML: {e}")
        print("\n===== Script Finished =====")
