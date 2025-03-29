import requests 

OLLAMA_URL="http://localhost:11434/api/generate" 

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

if __name__ == "__main__": 
    models = ["deepseek-coder:1.3b", "mistral", "llama2:13b"] 
    prompt = "What is the capital of France?" 

    for model in models: 
        print(f"\n Model: {model}") 
        print(query_model(model, prompt)) 
