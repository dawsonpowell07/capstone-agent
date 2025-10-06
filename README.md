python3 -m uvicorn main:app --reload


docker build -t my-fastapi-app .

docker run -p 8000:8000 my-fastapi-app
