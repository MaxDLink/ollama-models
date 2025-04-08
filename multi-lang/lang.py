import requests
import time
import psutil
import pynvml  # For NVIDIA GPU monitoring
from datetime import datetime
import os      # Added for file path operations

OLLAMA_URL = "http://localhost:11434/api/generate"

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

def get_gpu_usage(handle):
    """Get GPU utilization percentage."""
    if handle is None:
        return "N/A"
    try:
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        return util.gpu  # GPU utilization as a percentage
    except pynvml.NVMLError:
        return "Error"

def query_model(model_name, prompt):
    """Query the model and measure CPU/GPU usage."""
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }
    
    # Start resource monitoring
    start_time = time.time()
    process = psutil.Process()  # Current process
    cpu_before = process.cpu_percent(interval=None)  # Baseline CPU usage
    
    # Make the API call
    response = requests.post(OLLAMA_URL, json=payload)
    
    # Measure resources after the call
    cpu_after = process.cpu_percent(interval=None)  # CPU usage after call
    elapsed_time = time.time() - start_time
    
    # Average CPU usage (approximation)
    cpu_usage = (cpu_before + cpu_after) / 2 if cpu_before != cpu_after else cpu_after
    
    return {
        "response": response.json()["response"] if response.status_code == 200 else f"Error: {response.status_code} - {response.text}",
        "cpu_usage": cpu_usage,
        "elapsed_time": elapsed_time
    }

if __name__ == "__main__":
    models = ["deepseek-coder:1.3b", "mistral", "llama2:13b"]

    # Test phrases in different languages
    test_phrases = {
        "Spanish": "El perro corre rápido en el parque.",
        "French": "Le chat dort sur le canapé toute la journée.",
        "German": "Die Sonne scheint heute sehr hell."
    }
    
    target_language = "English"

    # Initialize GPU monitoring
    gpu_handle = initialize_gpu()

    # Determine the output file path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_md_file = os.path.join(script_dir, "lang_output.md") # Changed output filename to .md

    # Clear the output file at the start (optional)
    # with open(output_md_file, 'w', encoding='utf-8') as f:
    #     f.write(f"# Multi-Language Translation Test - {datetime.now()}\n\n")

    # Test each model
    for model in models:
        print(f"\nModel: {model}")
        print(f"Testing translation to {target_language}:\n")

        # Write model header to MD file
        try:
            with open(output_md_file, 'a', encoding='utf-8') as f_md:
                f_md.write(f"## Model: {model}\n\n")
        except IOError as e:
            print(f"Error writing header for model {model} to {output_md_file}: {e}")
            continue # Skip this model if header writing fails

        for lang, phrase in test_phrases.items():
            prompt = f"Translate the following {lang} text into {target_language}: '{phrase}'"

            # Query model and get resource usage
            result = query_model(model, prompt)
            gpu_usage = get_gpu_usage(gpu_handle) if gpu_handle else "N/A"

            # Format output for console
            console_output = (
                f"Original ({lang}): {phrase}\n"
                f"Translation: {result['response']}\n"
                f"CPU Usage: {result['cpu_usage']:.2f}%\n"
                # Handle potential non-numeric GPU usage
                f"GPU Usage: {gpu_usage}%" if isinstance(gpu_usage, (int, float)) else f"GPU Usage: {gpu_usage}" + "\n"
                f"Time Taken: {result['elapsed_time']:.2f} seconds\n"
                f"{'-' * 50}\n"
            )

            # Print to console
            print(console_output)

            # Write detailed output to MD file
            try:
                with open(output_md_file, 'a', encoding='utf-8') as f_md:
                    f_md.write(f"### Original ({lang})\n")
                    f_md.write(f"```\n{phrase}\n```\n\n")
                    f_md.write(f"**Prompt:**\n```\n{prompt}\n```\n\n")
                    f_md.write(f"**Translation:**\n```\n{result['response']}\n```\n\n")
                    f_md.write("**Performance:**\n")
                    f_md.write(f"- CPU Usage: {result['cpu_usage']:.2f}%\n")
                    gpu_usage_str = f"{gpu_usage}%" if isinstance(gpu_usage, (int, float)) else str(gpu_usage)
                    f_md.write(f"- GPU Usage: {gpu_usage_str}\n")
                    f_md.write(f"- Time Taken: {result['elapsed_time']:.2f} seconds\n")
                    f_md.write("\n---\n\n")
            except IOError as e:
                print(f"Error writing result for {lang} to {output_md_file}: {e}")

    # Cleanup GPU monitoring
    if gpu_handle:
        pynvml.nvmlShutdown()

