## Code used for running models and experiments 

### Setup Instructions

0. Setup Ollama 

```bash 
    curl -fsSL https://ollama.com/install.sh | sh 
``` 

```bash 
    ollama pull deepseek-coder:1.3b 
    ollama pull mistral 
    ollama pull llama2:13b 
``` 

Ollama should run as a background process after install with curl, but in the event it does not you can try ollama serve below: 

```bash 
ollama serve 
``` 

1. Create and activate a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```


### How to Run 

1. Navigate into one of the following folders:


    Basic - general questions 

    Code - Simple coding questions 

    Text-sum - text summarization questions 

    Writing - creative writing questions 

    Multi-lang - multilingual capabilities 

2. The run command is: 

````bash 
python3 filename.py
```` 






