from pinecone import Pinecone, ServerlessSpec
from config import Config

def create_index_final():
    """Create index with correct environment using new Pinecone API"""
    try:
        # Initialize with new Pinecone API
        pc = Pinecone(api_key=Config.PINECONE_API_KEY)
        
        print("Connected to Pinecone")
        
        # Get existing indexes
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        
        # Create index using serverless (free tier)
        if Config.PINECONE_INDEX_NAME not in existing_indexes:
            pc.create_index(
                name=Config.PINECONE_INDEX_NAME,
                dimension=Config.PINECONE_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            print("✅ Serverless index created successfully!")
        else:
            print("Index already exists!")
            
        # List indexes to confirm
        indexes = [idx.name for idx in pc.list_indexes()]
        print(f"All indexes: {indexes}")
        
        # Show index stats
        if Config.PINECONE_INDEX_NAME in indexes:
            index = pc.Index(Config.PINECONE_INDEX_NAME)
            stats = index.describe_index_stats()
            print(f"Index stats: {stats}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_index_final()