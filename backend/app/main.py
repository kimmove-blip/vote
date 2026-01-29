"""
FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler for startup and shutdown."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="""
        Global Mobile Blockchain Voting System API

        A secure, transparent, and verifiable electronic voting system using:
        - Blockchain (Hyperledger Fabric) for immutable vote records
        - Homomorphic encryption (CGS) for privacy-preserving tallying
        - Zero-Knowledge Proofs (ZKP) for eligibility and validity verification
        - DID + FIDO2 for strong authentication

        ## Key Features
        - End-to-end verifiability
        - Voter privacy protection
        - Double-voting prevention
        - Threshold decryption (3-of-5)
        """,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Gzip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "version": settings.APP_VERSION}

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": f"{settings.API_V1_PREFIX}/docs"
        }

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS if not settings.DEBUG else 1,
    )
