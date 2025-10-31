import os
import sys
import requests
import time
import base64
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

# Add the root directory to the path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from config import Config

class GitHubScraper:
    def __init__(self, github_token: Optional[str] = None):
        """Initialize GitHub scraper with optional token for higher rate limits"""
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        
        if self.github_token:
            self.session.headers.update({
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            })
            print("✅ GitHub token configured - higher rate limits available")
        else:
            print("⚠️  No GitHub token - using public API (60 requests/hour limit)")
            
        # Supported file extensions for developers
        self.supported_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
            '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
            '.md', '.rst', '.txt', '.json', '.yaml', '.yml', '.xml', '.toml',
            '.sql', '.sh', '.bat', '.dockerfile', '.gitignore', '.env'
        }
    
    def get_rate_limit(self) -> Dict[str, Any]:
        """Check current GitHub API rate limit status"""
        try:
            response = self.session.get(f"{self.base_url}/rate_limit")
            if response.status_code == 200:
                return response.json()
            return {"error": f"Status {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_repository_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get basic repository information"""
        try:
            response = self.session.get(f"{self.base_url}/repos/{owner}/{repo}")
            if response.status_code == 200:
                repo_data = response.json()
                return {
                    "name": repo_data.get("name"),
                    "full_name": repo_data.get("full_name"),
                    "description": repo_data.get("description"),
                    "language": repo_data.get("language"),
                    "languages_url": repo_data.get("languages_url"),
                    "stars": repo_data.get("stargazers_count"),
                    "forks": repo_data.get("forks_count"),
                    "topics": repo_data.get("topics", []),
                    "default_branch": repo_data.get("default_branch", "main"),
                    "clone_url": repo_data.get("clone_url"),
                    "html_url": repo_data.get("html_url")
                }
            else:
                print(f"❌ Failed to get repo info: {response.status_code}")
                return {}
        except Exception as e:
            print(f"❌ Error getting repo info: {e}")
            return {}
    
    def get_repository_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Get programming languages used in the repository"""
        try:
            response = self.session.get(f"{self.base_url}/repos/{owner}/{repo}/languages")
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            print(f"❌ Error getting languages: {e}")
            return {}
    
    def get_repository_tree(self, owner: str, repo: str, branch: str = "main") -> List[Dict[str, Any]]:
        """Get the complete file tree of a repository"""
        try:
            # Get the tree recursively
            response = self.session.get(
                f"{self.base_url}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            )
            
            if response.status_code == 200:
                tree_data = response.json()
                files = []
                
                for item in tree_data.get("tree", []):
                    if item.get("type") == "blob":  # Only files, not directories
                        file_path = item.get("path", "")
                        file_extension = Path(file_path).suffix.lower()
                        
                        # Filter by supported extensions
                        if file_extension in self.supported_extensions:
                            files.append({
                                "path": file_path,
                                "sha": item.get("sha"),
                                "size": item.get("size", 0),
                                "url": item.get("url"),
                                "extension": file_extension,
                                "filename": Path(file_path).name
                            })
                
                print(f"📁 Found {len(files)} supported files in {owner}/{repo}")
                return files
            else:
                print(f"❌ Failed to get repository tree: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error getting repository tree: {e}")
            return []
    
    def get_file_content(self, owner: str, repo: str, file_path: str, sha: str = None) -> Optional[str]:
        """Get the content of a specific file"""
        try:
            if sha:
                # Use blob API for efficiency
                response = self.session.get(f"{self.base_url}/repos/{owner}/{repo}/git/blobs/{sha}")
            else:
                # Use contents API
                response = self.session.get(f"{self.base_url}/repos/{owner}/{repo}/contents/{file_path}")
            
            if response.status_code == 200:
                content_data = response.json()
                
                # Decode base64 content
                if content_data.get("encoding") == "base64":
                    content = base64.b64decode(content_data.get("content", "")).decode("utf-8", errors="ignore")
                    return content
                else:
                    return content_data.get("content", "")
            else:
                print(f"❌ Failed to get file {file_path}: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting file content for {file_path}: {e}")
            return None
    
    def scrape_repository(self, owner: str, repo: str, max_files: int = 100, 
                         max_file_size: int = 50000) -> List[Dict[str, Any]]:
        """Scrape a complete repository and return structured data"""
        print(f"🚀 Starting to scrape {owner}/{repo}")
        
        # Check rate limit
        rate_limit = self.get_rate_limit()
        remaining = rate_limit.get("rate", {}).get("remaining", 0)
        print(f"📊 GitHub API rate limit: {remaining} requests remaining")
        
        if remaining < 10:
            print("⚠️  Low rate limit remaining. Consider using a GitHub token.")
        
        # Get repository info
        repo_info = self.get_repository_info(owner, repo)
        if not repo_info:
            return []
        
        # Get languages
        languages = self.get_repository_languages(owner, repo)
        
        # Get file tree
        files = self.get_repository_tree(owner, repo, repo_info.get("default_branch", "main"))
        
        # Filter files by size and limit count
        files = [f for f in files if f.get("size", 0) <= max_file_size]
        files = files[:max_files]
        
        print(f"📝 Processing {len(files)} files (max_files={max_files}, max_size={max_file_size})")
        
        scraped_data = []
        
        for i, file_info in enumerate(files):
            print(f"   Processing {i+1}/{len(files)}: {file_info['path']}")
            
            # Get file content
            content = self.get_file_content(owner, repo, file_info["path"], file_info.get("sha"))
            
            if content:
                file_data = {
                    "content": content,
                    "metadata": {
                        "repo_owner": owner,
                        "repo_name": repo,
                        "repo_full_name": repo_info.get("full_name"),
                        "repo_description": repo_info.get("description"),
                        "repo_language": repo_info.get("language"),
                        "repo_languages": languages,
                        "repo_stars": repo_info.get("stars"),
                        "repo_topics": repo_info.get("topics", []),
                        "file_path": file_info["path"],
                        "file_name": file_info["filename"],
                        "file_extension": file_info["extension"],
                        "file_size": file_info.get("size", 0),
                        "file_sha": file_info.get("sha"),
                        "source_url": f"https://github.com/{owner}/{repo}/blob/{repo_info.get('default_branch', 'main')}/{file_info['path']}",
                        "api_url": file_info.get("url"),
                        "content_type": "code" if file_info["extension"] in {'.py', '.js', '.java', '.cpp'} else "documentation",
                        "scraped_at": time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                }
                scraped_data.append(file_data)
            
            # Rate limiting - be respectful
            time.sleep(0.1)
        
        print(f"✅ Successfully scraped {len(scraped_data)} files from {owner}/{repo}")
        return scraped_data
    
    def save_scraped_data(self, scraped_data: List[Dict[str, Any]], output_dir: str = "scraped_repos"):
        """Save scraped data to local files for processing"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        if not scraped_data:
            print("❌ No data to save")
            return []
        
        # Group by repository
        repo_name = scraped_data[0]["metadata"]["repo_full_name"].replace("/", "_")
        repo_dir = output_path / repo_name
        repo_dir.mkdir(exist_ok=True)
        
        saved_files = []
        
        for i, file_data in enumerate(scraped_data):
            # Create safe filename
            original_path = file_data["metadata"]["file_path"]
            safe_filename = f"{i:03d}_{Path(original_path).name}"
            
            # Save content
            content_file = repo_dir / safe_filename
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(file_data["content"])
            
            # Save metadata
            metadata_file = repo_dir / f"{safe_filename}.meta.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(file_data["metadata"], f, indent=2)
            
            saved_files.append(str(content_file))
        
        print(f"💾 Saved {len(saved_files)} files to {repo_dir}")
        return saved_files

def main():
    """Interactive GitHub scraper"""
    print("🐙 DevRAG GitHub Repository Scraper")
    print("=" * 40)
    
    scraper = GitHubScraper()
    
    # Show rate limit
    rate_limit = scraper.get_rate_limit()
    if "rate" in rate_limit:
        remaining = rate_limit["rate"]["remaining"]
        total = rate_limit["rate"]["limit"]
        reset_time = rate_limit["rate"]["reset"]
        print(f"📊 Rate limit: {remaining}/{total} remaining")
    
    print("\n💡 Popular repositories to try:")
    print("   - fastapi/fastapi (Python web framework)")
    print("   - facebook/react (JavaScript library)")
    print("   - microsoft/vscode (TypeScript editor)")
    print("   - python/cpython (Python language)")
    
    while True:
        print("\n" + "=" * 40)
        repo_input = input("Enter repository (owner/repo) or 'quit': ").strip()
        
        if repo_input.lower() in ['quit', 'exit', 'q']:
            break
            
        if '/' not in repo_input:
            print("❌ Please use format: owner/repo (e.g., fastapi/fastapi)")
            continue
        
        try:
            owner, repo = repo_input.split('/', 1)
            
            # Ask for scraping options
            max_files = input("Max files to scrape (default 50): ").strip()
            max_files = int(max_files) if max_files.isdigit() else 50
            
            max_size = input("Max file size in bytes (default 50000): ").strip()
            max_size = int(max_size) if max_size.isdigit() else 50000
            
            # Scrape the repository
            scraped_data = scraper.scrape_repository(owner, repo, max_files, max_size)
            
            if scraped_data:
                # Save locally
                saved_files = scraper.save_scraped_data(scraped_data)
                
                print(f"\n✅ Scraped {len(scraped_data)} files")
                print(f"💾 Files saved to: scraped_repos/{owner}_{repo}/")
                print("\n🔄 Next: Run ingestion to add to vector database")
                print(f"   python src/ingestion/ingest.py")
            else:
                print("❌ No files scraped. Check repository name and rate limits.")
                
        except ValueError:
            print("❌ Invalid format. Use: owner/repo")
        except KeyboardInterrupt:
            print("\n👋 Scraping interrupted")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("👋 GitHub scraper finished")

if __name__ == "__main__":
    main()