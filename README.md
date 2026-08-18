## Setup

### Backend

1. Create `.env` file from template:
```bash
cp backend/.env.example backend/.env
```

2. Add your credentials to `backend/.env`:
```
BRIGHTDATA_API_KEY=your_actual_key_here
BRIGHTDATA_SCRAPERS={"theverge": "c_your_collector_id", ...}
```

3. Install dependencies:
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. Start the server:
```bash
uvicorn app.main:app --reload
```

### Frontend

1. Install dependencies:
```bash
cd frontend-react
npm install
```

2. Start dev server:
```bash
npm run dev
```