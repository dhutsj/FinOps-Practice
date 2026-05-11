FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir boto3 python-dateutil requests

COPY aws_cost.py .

CMD ["python", "aws_cost.py"]
