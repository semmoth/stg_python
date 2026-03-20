# stg_python

What was built
golf-tracker/
├── app.py                    # Login + home
├── requirements.txt
├── config.yaml               # User auth config (fill in passwords)
├── hash_password.py          # Generates hashed passwords for config.yaml
├── setup_db.py               # One-time DB setup + seeds Gullbringa
├── .streamlit/secrets.toml   # Your Turso credentials (fill in)
├── db/
│   ├── client.py             # Turso HTTP client (pure Python, no binaries)
│   └── queries.py            # All DB operations
├── utils/
│   ├── constants.py          # Clubs, surfaces, tees
│   └── strokes_gained.py     # Full SG calculations ported from R
├── pages/
│   ├── 1_Data_Entry.py       # Hole-by-hole entry
│   ├── 2_Last_Round.py       # Last round stats + charts
│   ├── 3_Summary.py          # Season trends + STG history
│   └── 4_Course_Admin.py     # Update Gullbringa par/distances
└── data/
    ├── distance_sg.csv        # (copied from your R project)
    └── proputting3.csv        # (copied from your R project)

How to get started (step by step)
1. Install Python packages

pip install -r requirements.txt

2. Create a Turso account + database

Go to turso.tech → sign up free → create a database → click "Connect" → copy the URL and token
3. Fill in .streamlit/secrets.toml

TURSO_URL = "https://your-db.turso.io"
TURSO_TOKEN = "your-token"

4. Set up the database

python setup_db.py

5. Set passwords for users

python hash_password.py

Paste the output into config.yaml — update the names/emails for your friends too.

6. Run the app

streamlit run app.py

7. Go to Course Admin and enter the actual par + distance for each Gullbringa hole (the current values are placeholders).
