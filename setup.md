# Setup Commands

## 1) Go to project root (what: open project folder)
```bash
cd "/Users/balajikartheek/Desktop/Websites/Dementia/Dimentia-Bot-main"
```

## 2) Activate virtual environment (what: use project Python)
```bash
source .venv/bin/activate
```

## 3) Install all dependencies (what: install required packages)
```bash
pip install -r requirements.txt
```

## 4) Ensure Gemini SDK is installed (what: Gemini model integration)
```bash
pip install google-genai
```

## 5) Install spaCy English model (what: NLP/entity extraction)
```bash
pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
```

## 6) Add Gemini API key (what: enable Gemini responses)
```bash
echo 'GEMINI_API_KEY="YOUR_GEMINI_API_KEY"' > .env
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
```

## 7) Start app (what: run chatbot UI)
```bash
python run.py
```

## 8) If port 8501 is busy (what: run on another port)
```bash
streamlit run main.py --server.port 8502 --server.address localhost --browser.gatherUsageStats false
```

## 9) Quick sanity check (what: verify critical imports)
```bash
python -c "import streamlit, whisper, sentence_transformers, spacy, faiss, torch, google.genai; print('all good')"
```
