release: cd app && alembic upgrade head
web: cd app && uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers