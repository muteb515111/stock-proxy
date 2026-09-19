from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "OK", "version": "4.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}
