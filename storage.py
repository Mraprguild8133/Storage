import json
import os
from typing import Dict, List, Any
from datetime import datetime

class Storage:
    def __init__(self, storage_file: str = "data.json"):
        self.storage_file = storage_file
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """Load data from JSON file"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                print(f"Warning: Could not load storage file: {e}")
        
        # Initialize with default structure
        return {
            "files": {},
            "users": {},
            "stats": {
                "total_files": 0,
                "total_users": 0,
                "total_size": 0,
                "files_by_type": {
                    "document": 0,
                    "photo": 0,
                    "video": 0,
                    "audio": 0
                }
            }
        }
    
    def _save_data(self):
        """Save data to JSON file"""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def add_file(self, file_data: Dict[str, Any]):
        """Add a new file to storage"""
        file_id = file_data['file_id']
        user_id = file_data['user_id']
        
        # Add to files
        self.data["files"][file_id] = file_data
        
        # Add to user's file list
        if str(user_id) not in self.data["users"]:
            self.data["users"][str(user_id)] = []
        
        if file_id not in self.data["users"][str(user_id)]:
            self.data["users"][str(user_id)].append(file_id)
        
        # Update statistics
        self.data["stats"]["total_files"] = len(self.data["files"])
        self.data["stats"]["total_users"] = len(self.data["users"])
        self.data["stats"]["total_size"] += file_data.get('file_size', 0)
        
        file_type = file_data['type']
        if file_type in self.data["stats"]["files_by_type"]:
            self.data["stats"]["files_by_type"][file_type] += 1
        
        self._save_data()
    
    def get_file(self, file_id: str) -> Dict[str, Any]:
        """Get file data by ID"""
        return self.data["files"].get(file_id)
    
    def get_user_files(self, user_id: int) -> List[str]:
        """Get all file IDs for a user"""
        return self.data["users"].get(str(user_id), [])
    
    def get_all_users(self) -> List[int]:
        """Get all user IDs"""
        return [int(user_id) for user_id in self.data["users"].keys()]
    
    def delete_file(self, file_id: str):
        """Delete a file from storage"""
        if file_id in self.data["files"]:
            file_data = self.data["files"][file_id]
            user_id = file_data['user_id']
            
            # Remove from files
            del self.data["files"][file_id]
            
            # Remove from user's file list
            if str(user_id) in self.data["users"]:
                if file_id in self.data["users"][str(user_id)]:
                    self.data["users"][str(user_id)].remove(file_id)
                
                # Remove user if no files left
                if not self.data["users"][str(user_id)]:
                    del self.data["users"][str(user_id)]
            
            # Update statistics
            self.data["stats"]["total_files"] = len(self.data["files"])
            self.data["stats"]["total_users"] = len(self.data["users"])
            self.data["stats"]["total_size"] -= file_data.get('file_size', 0)
            
            file_type = file_data['type']
            if file_type in self.data["stats"]["files_by_type"]:
                self.data["stats"]["files_by_type"][file_type] = max(0, 
                    self.data["stats"]["files_by_type"][file_type] - 1)
            
            self._save_data()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bot statistics"""
        return self.data["stats"]
    
    def search_files(self, user_id: int, query: str) -> List[Dict[str, Any]]:
        """Search files by name or caption"""
        results = []
        user_files = self.get_user_files(user_id)
        
        for file_id in user_files:
            file_data = self.get_file(file_id)
            if (query.lower() in file_data['name'].lower() or 
                query.lower() in file_data['caption'].lower()):
                results.append(file_data)
        
        return results
    
    def cleanup_orphaned_files(self):
        """Remove files that no longer have associated users"""
        files_to_remove = []
        
        for file_id, file_data in self.data["files"].items():
            user_id = file_data['user_id']
            if str(user_id) not in self.data["users"] or file_id not in self.data["users"][str(user_id)]:
                files_to_remove.append(file_id)
        
        for file_id in files_to_remove:
            self.delete_file(file_id)
        
        return len(files_to_remove)
