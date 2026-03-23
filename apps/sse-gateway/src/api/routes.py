from fastapi import APIRouter

router = APIRouter()

@router.get("/healthz/live")
def liveness():
    return {"status": "live"}

@router.get("/healthz/ready")
def readiness():
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info():
    import os
    info: dict = {"service": "sse-gateway"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info

