import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from startup import startup_event
from routes import vectors, admin, student

app = FastAPI(title="Student Learning API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -------------------------------------------------
# Startup
# -------------------------------------------------
@app.on_event("startup")
async def on_startup():
    await startup_event(app)

# -------------------------------------------------
# Routers
# -------------------------------------------------
app.include_router(
    student.router,
    prefix="/student",
    tags=["Student"]
    )

app.include_router(
    admin.router, 
    prefix="/admin", 
    tags=["Admin"]
    )

app.include_router(
    vectors.router, 
    prefix="/vectors", 
    tags=["Vectors"]
    )
