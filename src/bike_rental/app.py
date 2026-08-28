from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def hi():
    return {"message": "hello"}
