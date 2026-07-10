From python:3.12-slim

WORKDIR /app

COPY requirements-cpu.txt .

RUN pip install --no-cache-dir -r requirements-cpu.txt

COPY . .

EXPOSE 8000

CMD ["python","manage.py","runserver","0.0.0.0:8000"]