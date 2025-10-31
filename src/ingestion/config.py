import os
from typing import Optional

class Config:
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # AWS Configuration
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = "devrag-dev-docs-181457676035"
    
    # Pinecone Configuration  
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX_NAME: str = "devrag-index"
    PINECONE_DIMENSION: int = 1536  # text-embedding-3-small dimension
    
    # Application Configuration
    MAX_CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    MAX_TOKENS: int = 4000
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that all required environment variables are set"""
        required_vars = [
            cls.OPENAI_API_KEY,
            cls.PINECONE_API_KEY
        ]
        return all(var for var in required_vars)