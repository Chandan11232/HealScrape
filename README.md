## Setup

### Backend

1. Create `.env` file from template:
```bash
cp backend/.env.example backend/.env
```

2. Add your credentials:
BRIGHT_DATA_API_KEY=your_actual_key_here
BRIGHT_DATA_ACCOUNT_ID=your_account_id_here

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
cd frontend
npm install react-router-dom lucide-react --legacy-peer-deps
```

2. Start dev server:
```bash
npm run dev
```