release: cd app && alembic upgrade head
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers