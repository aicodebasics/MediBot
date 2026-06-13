# MediBot
Assignment: React pipeline from CodeBasics
Steps to Run This App

# 1. Clone the repo
git clone https://github.com/aicodebasics/MediBot
cd MediBot

# 2. ── BACKEND ──
cd backend

# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

# Create your .env file
copy .env.example .env
# Then open .env and set: GROQ_API_KEY=your-key-here

# Run ingestion (first time only — downloads models + parses PDFs)
python ingest.py

# Start the backend
uvicorn main:app --reload --port 8000

# 3. ── FRONTEND (new terminal) ──
cd ..\frontend
npm install

npm run dev

Then open http://localhost:3000
