import pinecone
from config import Config

def check_available_environments():
    """Check what environments are available"""
    
    # Common Pinecone environments to try
    environments = [
        "us-east-1-aws",
        "us-west1-gcp", 
        "asia-northeast1-gcp",
        "us-central1-gcp",
        "gcp-starter",
        "aws-starter"
    ]
    
    for env in environments:
        try:
            print(f"Trying environment: {env}")
            pinecone.init(api_key=Config.PINECONE_API_KEY, environment=env)
            
            # Try to list indexes (this will fail if env doesn't exist)
            indexes = pinecone.list_indexes()
            print(f"✅ SUCCESS: {env} works!")
            print(f"   Indexes: {indexes}")
            
            # Try to get more info
            try:
                info = pinecone.whoami()
                print(f"   Account info: {info}")
            except:
                pass
                
            break
            
        except Exception as e:
            print(f"❌ FAILED: {env} - {str(e)[:100]}")
    
    print("\n🔍 Check your Pinecone dashboard for the correct environment name!")

if __name__ == "__main__":
    check_available_environments()