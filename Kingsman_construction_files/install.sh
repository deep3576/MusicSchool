cd ~/KingsmanConstruction
# (Re)create venv with the same Python your web app uses (looks like 3.12)
python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python - << 'PY'
import pymysql, flask, flask_sqlalchemy, flask_login
print("OK  PyMySQL:", pymysql.__version__)
PY
