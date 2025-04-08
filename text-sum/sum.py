import requests
import PyPDF2
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

# Modified query_model to measure CPU and timing
def query_model(model_name, prompt):
    """Query the model and measure CPU/GPU usage."""
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }
    
    # Added resource monitoring
    start_time = time.time()              # Start timing
    process = psutil.Process()            # Get current process for CPU tracking
    cpu_before = process.cpu_percent(interval=None)  # Baseline CPU usage
    
    # Original API call
    response = requests.post(OLLAMA_URL, json=payload)
    
    # Measure resources after the call
    cpu_after = process.cpu_percent(interval=None)  # CPU usage after call
    elapsed_time = time.time() - start_time       # Calculate elapsed time
    
    # Average CPU usage (approximation)
    cpu_usage = (cpu_before + cpu_after) / 2 if cpu_before != cpu_after else cpu_after
    
    # Modified return to include resource data
    if response.status_code == 200:
        return {
            "response": response.json()["response"],
            "cpu_usage": cpu_usage,
            "elapsed_time": elapsed_time
        }
    else:
        return {
            "response": f"Error: {response.status_code} - {response.text}",
            "cpu_usage": cpu_usage,
            "elapsed_time": elapsed_time
        }

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

if __name__ == "__main__":
    models = ["deepseek-coder:1.3b", "mistral", "llama2:13b"]

    pdf_path = "/home/max/ollama-models/models/pyCrashCourse.pdf"
    pdf_text = extract_text_from_pdf(pdf_path)

    # Added GPU initialization
    gpu_handle = initialize_gpu()

    # Determine the output file path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_md_file = os.path.join(script_dir, "sum_output.md") # Changed filename

    # Clear the output file at the start (optional)
    # with open(output_md_file, 'w', encoding='utf-8') as f:
    #     f.write("# PDF Summarization Test\n\n")

    if pdf_text.startswith("Error"):
        print(pdf_text)
        # Optionally write error to the MD file
        # try:
        #     with open(output_md_file, 'a', encoding='utf-8') as f:
        #         f.write(f"## Error\n\nFailed to read PDF: {pdf_path}\n\n```\n{pdf_text}\n```\n\n---\n\n")
        # except IOError as e:
        #     print(f"Error writing PDF error to file {output_md_file}: {e}")
    else:
        text_sum = f"Please summarize this text from Python Crash Course:\n\n{pdf_text[:2000]}"  # Limiting to 2000 chars

        for model in models:
            print(f"\nModel: {model}")

            # Query model with resource tracking
            result = query_model(model, text_sum)

            # Get GPU usage
            gpu_usage = get_gpu_usage(gpu_handle) if gpu_handle else "N/A"

            # Print results with resource usage (console)
            print(f"Summary: {result['response']}")
            print(f"CPU Usage: {result['cpu_usage']:.2f}%")
            print(f"GPU Usage: {gpu_usage}%")
            print(f"Time Taken: {result['elapsed_time']:.2f} seconds")
            print("-" * 50)

            # Write response and resource usage to Markdown file
            try:
                with open(output_md_file, 'a', encoding='utf-8') as f:
                    f.write(f"## Model: {model}\n\n")
                    # Optionally include the truncated text in the prompt section
                    # f.write(f"**Prompt (Summarize Text Below):**\n```\n{text_sum}\n```\n\n")
                    f.write(f"**Prompt:**\n```\nPlease summarize this text from Python Crash Course: [Text from {os.path.basename(pdf_path)} - first 2000 chars]\n```\n\n")
                    f.write(f"**Summary:**\n```\n{result['response']}\n```\n\n")
                    f.write("**Performance:**\n")
                    f.write(f"- CPU Usage: {result['cpu_usage']:.2f}%\n")
                    gpu_usage_str = f"{gpu_usage}%" if isinstance(gpu_usage, (int, float)) else str(gpu_usage)
                    f.write(f"- GPU Usage: {gpu_usage_str}\n")
                    f.write(f"- Time Taken: {result['elapsed_time']:.2f} seconds\n")
                    f.write("\n---\n\n")
            except IOError as e:
                print(f"Error writing to file {output_md_file}: {e}")

    # Added GPU cleanup
    if gpu_handle:
        pynvml.nvmlShutdown()
