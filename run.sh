cd TheSpiritSchool
python -m venv .venv
# mac/linux
source .venv/bin/activate
# windows
# .venv\Scripts\activate

pip install -r requirements.txt

# create your real .env
cp .env.example .env

# initialize DB + create admin user
flask --app run.py init-db
flask --app run.py create-admin

# run
flask --app run.py run
