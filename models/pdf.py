import requests 
import PyPDF2

OLLAMA_URL = "http://localhost:11434/api/generate" 

def query_model(model_name, prompt): 
    payload = {
        "model": model_name, 
        "prompt": prompt, 
        "stream": False
    } 
    response = requests.post(OLLAMA_URL, json=payload) 
    if response.status_code == 200: 
        return response.json()["response"] 
    else: 
        return f"Error: {response.status_code} - {response.text}" 

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
    
    
    if pdf_text.startswith("Error"):
        print(pdf_text)
    else:
        
        text_sum = f"Please summarize this text from Python Crash Course:\n\n{pdf_text[:2000]}"  # Limiting to 2000 chars because of local LLMs max token restraint 
        
        
        for model in models: 
            print(f"\nModel: {model}") 
            response = query_model(model, text_sum)
            print(f"Summary: {response}")
