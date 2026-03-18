from fastapi import FastAPI
from .router import router

app = FastAPI(title="2D Nesting API")

app.include_router(router)