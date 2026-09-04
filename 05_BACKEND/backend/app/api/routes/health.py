from fastapi import APIRouter


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Report whether the API is running."""
    return {"status": "ok"}
