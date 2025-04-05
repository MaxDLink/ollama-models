import requests 

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

if __name__ == "__main__": 
    models = ["deepseek-coder:1.3b", "mistral", "llama2:13b"]

    # Test phrases in different languages
    test_phrases = {
        "Spanish": "El perro corre rápido en el parque.",
        "French": "Le chat dort sur le canapé toute la journée.",
        "German": "Die Sonne scheint heute sehr hell."
    }

    # Target language for translation
    target_language = "English"

    # Test each model
    for model in models: 
        print(f"\nModel: {model}")
        print(f"Testing translation to {target_language}:\n")
        
        for lang, phrase in test_phrases.items():
            # Construct the translation prompt
            prompt = f"Translate the following {lang} text into {target_language}: '{phrase}'"
            result = query_model(model, prompt)
            
            # Print the original phrase and the translation
            print(f"Original ({lang}): {phrase}")
            print(f"Translation: {result}")
            print("-" * 50)
