import json
import os
from typing import Dict, List, Optional
from datetime import datetime

class Storage:
    def __init__(self, storage_file: str = "files.json"):
        self.storage_file = storage_file
        self.files = {}  # Initialize files dictionary
        self.users = {}  # Initialize users dictionary
        self.load_data()
    
    def load_data(self):
        """Load data from JSON file"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.files = data.get('files', {})
                    self.users = data.get('users', {})
            else:
                self.files = {}
                self.users = {}
                self.save_data()
        except Exception as e:
            print(f"Error loading data: {e}")
            self.files = {}
            self.users = {}
            self.save_data()
    
    def save_data(self):
        """Save data to JSON file"""
        try:
            data = {
                'files': self.files,
                'users': self.users
            }
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def add_file(self, file_data: Dict) -> bool:
        """Add a new file to storage"""
        try:
            file_id = file_data['file_id']
            user_id = str(file_data['user_id'])  # Convert to string for JSON compatibility
            
            # Store file data
            self.files[file_id] = file_data
            
            # Update user's file list
            if user_id not in self.users:
                self.users[user_id] = {
                    'user_name': file_data['user_name'],
                    'files': [],
                    'first_seen': datetime.now().isoformat(),
                    'last_seen': datetime.now().isoformat()
                }
            
            if file_id not in self.users[user_id]['files']:
                self.users[user_id]['files'].append(file_id)
            
            self.users[user_id]['last_seen'] = datetime.now().isoformat()
            
            self.save_data()
            return True
            
        except Exception as e:
            print(f"Error adding file: {e}")
            return False
    
    def get_file(self, file_id: str) -> Optional[Dict]:
        """Get file data by file_id"""
        return self.files.get(file_id)
    
    def get_user_files(self, user_id: int) -> List[Dict]:
        """Get all file data for a user"""
        try:
            user_id_str = str(user_id)
            if user_id_str in self.users:
                file_ids = self.users[user_id_str]['files']
                files = []
                for file_id in file_ids:
                    file_data = self.get_file(file_id)
                    if file_data:
                        files.append(file_data)
                return files
            return []
        except Exception as e:
            print(f"Error getting user files: {e}")
            return []
    
    def delete_file(self, file_id: str) -> bool:
        """Delete a file from storage"""
        try:
            if file_id in self.files:
                file_data = self.files[file_id]
                user_id = str(file_data['user_id'])
                
                # Remove from user's file list
                if user_id in self.users and file_id in self.users[user_id]['files']:
                    self.users[user_id]['files'].remove(file_id)
                
                # Remove file data
                del self.files[file_id]
                
                self.save_data()
                return True
            return False
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
    
    def search_files(self, user_id: int, query: str) -> List[Dict]:
        """Search files by name or caption for a specific user"""
        results = []
        query = query.lower()
        
        user_files = self.get_user_files(user_id)
        for file_data in user_files:
            if file_data:
                if (query in file_data['name'].lower() or 
                    query in file_data['caption'].lower()):
                    results.append(file_data)
        
        return results
    
    def get_stats(self) -> Dict:
        """Get bot statistics"""
        try:
            total_files = len(self.files)
            total_users = len(self.users)
            
            # Calculate total size and files by type
            total_size = 0
            files_by_type = {}
            
            for file_id, file_data in self.files.items():
                file_size = file_data.get('file_size', 0)
                total_size += file_size
                
                file_type = file_data.get('type', 'unknown')
                files_by_type[file_type] = files_by_type.get(file_type, 0) + 1
            
            return {
                'total_files': total_files,
                'total_users': total_users,
                'total_size': total_size,
                'files_by_type': files_by_type
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {
                'total_files': 0,
                'total_users': 0,
                'total_size': 0,
                'files_by_type': {}
            }
    
    def get_all_users(self) -> List[int]:
        """Get list of all user IDs"""
        try:
            return [int(user_id) for user_id in self.users.keys()]
        except:
            return []