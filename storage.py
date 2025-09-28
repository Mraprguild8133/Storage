import json
import os
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

class Storage:
    def __init__(self, storage_file: str = "data.json", backup_interval: int = 24):
        self.storage_file = storage_file
        self.backup_interval = backup_interval  # hours
        self.last_backup = None
        self.data = self._load_data()
        
        # Create backup on initialization
        self._create_backup()
    
    def _load_data(self) -> Dict[str, Any]:
        """Load data from JSON file with proper error handling"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"✅ Storage loaded: {len(data.get('files', {}))} files, {len(data.get('users', {}))} users")
                    return data
            except json.JSONDecodeError as e:
                print(f"❌ Corrupted storage file: {e}. Creating new one.")
                # Try to create backup of corrupted file
                self._backup_corrupted_file()
            except Exception as e:
                print(f"❌ Error loading storage: {e}. Creating new one.")
        
        # Initialize with default structure
        default_data = {
            "files": {},
            "users": {},
            "settings": {
                "created_at": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
                "version": "1.0"
            },
            "stats": {
                "total_files": 0,
                "total_users": 0,
                "total_size": 0,
                "files_by_type": {
                    "document": 0,
                    "photo": 0,
                    "video": 0,
                    "audio": 0
                },
                "daily_uploads": {},
                "user_activity": {}
            }
        }
        
        print("✅ New storage initialized")
        return default_data
    
    def _save_data(self):
        """Save data to JSON file with backup and error handling"""
        try:
            # Update last modified timestamp
            self.data["settings"]["last_modified"] = datetime.now().isoformat()
            
            # Create backup if needed
            self._auto_backup()
            
            # Save to temporary file first
            temp_file = self.storage_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False, default=str)
            
            # Replace original file
            if os.path.exists(self.storage_file):
                os.replace(temp_file, self.storage_file)
            else:
                os.rename(temp_file, self.storage_file)
                
            print(f"💾 Storage saved: {len(self.data['files'])} files, {len(self.data['users'])} users")
            
        except Exception as e:
            print(f"❌ Error saving data: {e}")
            # Try to save backup on error
            self._emergency_backup()
    
    def _create_backup(self):
        """Create a backup of the current data"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"backup_{timestamp}.json"
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False, default=str)
            
            self.last_backup = datetime.now()
            print(f"📦 Backup created: {backup_file}")
            
            # Clean up old backups (keep last 5)
            self._cleanup_old_backups()
            
        except Exception as e:
            print(f"❌ Error creating backup: {e}")
    
    def _auto_backup(self):
        """Automatically create backup if interval has passed"""
        if self.last_backup is None:
            self._create_backup()
            return
        
        time_diff = datetime.now() - self.last_backup
        if time_diff.total_seconds() >= self.backup_interval * 3600:
            self._create_backup()
    
    def _backup_corrupted_file(self):
        """Backup corrupted file for analysis"""
        try:
            if os.path.exists(self.storage_file):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                corrupted_backup = f"corrupted_{timestamp}.json"
                os.rename(self.storage_file, corrupted_backup)
                print(f"🚨 Corrupted file backed up as: {corrupted_backup}")
        except Exception as e:
            print(f"❌ Error backing up corrupted file: {e}")
    
    def _emergency_backup(self):
        """Create emergency backup when normal save fails"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_emergency")
            emergency_file = f"emergency_{timestamp}.json"
            
            with open(emergency_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"🚨 Emergency backup created: {emergency_file}")
        except Exception as e:
            print(f"❌ Critical: Could not create emergency backup: {e}")
    
    def _cleanup_old_backups(self, keep_count: int = 5):
        """Clean up old backup files"""
        try:
            backup_files = [f for f in os.listdir('.') if f.startswith('backup_') and f.endswith('.json')]
            backup_files.sort(reverse=True)  # Sort by newest first
            
            # Remove old backups
            for old_backup in backup_files[keep_count:]:
                os.remove(old_backup)
                print(f"🗑️ Removed old backup: {old_backup}")
                
        except Exception as e:
            print(f"❌ Error cleaning up backups: {e}")
    
    def add_file(self, file_data: Dict[str, Any]):
        """Add a new file to storage with enhanced tracking"""
        file_id = file_data['file_id']
        user_id = file_data['user_id']
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Add to files
        self.data["files"][file_id] = file_data
        
        # Add to user's file list
        user_key = str(user_id)
        if user_key not in self.data["users"]:
            self.data["users"][user_key] = {
                "files": [],
                "first_seen": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "total_files": 0,
                "total_size": 0
            }
        
        if file_id not in self.data["users"][user_key]["files"]:
            self.data["users"][user_key]["files"].append(file_id)
        
        # Update user statistics
        self.data["users"][user_key]["last_active"] = datetime.now().isoformat()
        self.data["users"][user_key]["total_files"] = len(self.data["users"][user_key]["files"])
        self.data["users"][user_key]["total_size"] += file_data.get('file_size', 0)
        
        # Update global statistics
        self.data["stats"]["total_files"] = len(self.data["files"])
        self.data["stats"]["total_users"] = len(self.data["users"])
        self.data["stats"]["total_size"] += file_data.get('file_size', 0)
        
        # Update file type statistics
        file_type = file_data['type']
        if file_type in self.data["stats"]["files_by_type"]:
            self.data["stats"]["files_by_type"][file_type] += 1
        
        # Update daily upload statistics
        if current_date not in self.data["stats"]["daily_uploads"]:
            self.data["stats"]["daily_uploads"][current_date] = 0
        self.data["stats"]["daily_uploads"][current_date] += 1
        
        # Update user activity
        if user_key not in self.data["stats"]["user_activity"]:
            self.data["stats"]["user_activity"][user_key] = 0
        self.data["stats"]["user_activity"][user_key] += 1
        
        self._save_data()
        
        print(f"✅ File added: {file_data['name']} by user {user_id}")
    
    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file data by ID"""
        return self.data["files"].get(file_id)
    
    def get_user_files(self, user_id: int) -> List[str]:
        """Get all file IDs for a user"""
        user_key = str(user_id)
        if user_key in self.data["users"]:
            return self.data["users"][user_key]["files"]
        return []
    
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed user information"""
        user_key = str(user_id)
        return self.data["users"].get(user_key)
    
    def get_all_users(self) -> List[int]:
        """Get all user IDs"""
        return [int(user_id) for user_id in self.data["users"].keys()]
    
    def get_all_files(self) -> List[Dict[str, Any]]:
        """Get all files data"""
        return list(self.data["files"].values())
    
    def delete_file(self, file_id: str) -> bool:
        """Delete a file from storage"""
        if file_id in self.data["files"]:
            file_data = self.data["files"][file_id]
            user_id = file_data['user_id']
            user_key = str(user_id)
            
            # Remove from files
            del self.data["files"][file_id]
            
            # Remove from user's file list and update user stats
            if user_key in self.data["users"]:
                if file_id in self.data["users"][user_key]["files"]:
                    self.data["users"][user_key]["files"].remove(file_id)
                    self.data["users"][user_key]["total_files"] = len(self.data["users"][user_key]["files"])
                    self.data["users"][user_key]["total_size"] = max(0, 
                        self.data["users"][user_key]["total_size"] - file_data.get('file_size', 0))
                
                # Remove user if no files left
                if not self.data["users"][user_key]["files"]:
                    del self.data["users"][user_key]
            
            # Update global statistics
            self.data["stats"]["total_files"] = len(self.data["files"])
            self.data["stats"]["total_users"] = len(self.data["users"])
            self.data["stats"]["total_size"] = max(0, 
                self.data["stats"]["total_size"] - file_data.get('file_size', 0))
            
            # Update file type statistics
            file_type = file_data['type']
            if file_type in self.data["stats"]["files_by_type"]:
                self.data["stats"]["files_by_type"][file_type] = max(0, 
                    self.data["stats"]["files_by_type"][file_type] - 1)
            
            self._save_data()
            
            print(f"🗑️ File deleted: {file_data['name']}")
            return True
        
        return False
    
    def delete_user_files(self, user_id: int) -> int:
        """Delete all files for a user"""
        user_key = str(user_id)
        if user_key not in self.data["users"]:
            return 0
        
        deleted_count = 0
        user_files = self.data["users"][user_key]["files"].copy()
        
        for file_id in user_files:
            if self.delete_file(file_id):
                deleted_count += 1
        
        print(f"🗑️ Deleted {deleted_count} files for user {user_id}")
        return deleted_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive bot statistics"""
        stats = self.data["stats"].copy()
        
        # Add calculated statistics
        stats["average_file_size"] = (
            stats["total_size"] / stats["total_files"] 
            if stats["total_files"] > 0 else 0
        )
        
        # Calculate active users (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        active_users = 0
        
        for user_key, user_data in self.data["users"].items():
            last_active = datetime.fromisoformat(user_data["last_active"])
            if last_active > thirty_days_ago:
                active_users += 1
        
        stats["active_users"] = active_users
        
        # Calculate storage distribution
        stats["storage_distribution"] = {}
        for file_type in ["document", "photo", "video", "audio"]:
            stats["storage_distribution"][file_type] = 0
        
        for file_data in self.data["files"].values():
            file_type = file_data['type']
            if file_type in stats["storage_distribution"]:
                stats["storage_distribution"][file_type] += file_data.get('file_size', 0)
        
        return stats
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get very detailed statistics for admin panel"""
        basic_stats = self.get_stats()
        
        # Add file size distribution
        size_ranges = {
            "0-1MB": 0,
            "1-10MB": 0,
            "10-50MB": 0,
            "50-100MB": 0,
            "100MB+": 0
        }
        
        for file_data in self.data["files"].values():
            size_mb = file_data.get('file_size', 0) / (1024 * 1024)
            if size_mb < 1:
                size_ranges["0-1MB"] += 1
            elif size_mb < 10:
                size_ranges["1-10MB"] += 1
            elif size_mb < 50:
                size_ranges["10-50MB"] += 1
            elif size_mb < 100:
                size_ranges["50-100MB"] += 1
            else:
                size_ranges["100MB+"] += 1
        
        basic_stats["size_distribution"] = size_ranges
        
        # Add top users
        top_users = []
        for user_key, user_data in self.data["users"].items():
            top_users.append({
                "user_id": int(user_key),
                "file_count": user_data["total_files"],
                "total_size": user_data["total_size"],
                "last_active": user_data["last_active"]
            })
        
        top_users.sort(key=lambda x: x["file_count"], reverse=True)
        basic_stats["top_users"] = top_users[:10]  # Top 10 users
        
        # Add recent activity (last 7 days)
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_uploads = 0
        
        for file_data in self.data["files"].values():
            upload_time = datetime.fromisoformat(file_data['upload_time'])
            if upload_time > seven_days_ago:
                recent_uploads += 1
        
        basic_stats["recent_uploads"] = recent_uploads
        
        return basic_stats
    
    def search_files(self, user_id: int, query: str) -> List[Dict[str, Any]]:
        """Search files by name or caption for a specific user"""
        results = []
        user_files = self.get_user_files(user_id)
        query_lower = query.lower()
        
        for file_id in user_files:
            file_data = self.get_file(file_id)
            if file_data:
                if (query_lower in file_data['name'].lower() or 
                    query_lower in file_data['caption'].lower()):
                    results.append(file_data)
        
        return results
    
    def search_all_files(self, query: str) -> List[Dict[str, Any]]:
        """Search all files (admin function)"""
        results = []
        query_lower = query.lower()
        
        for file_data in self.data["files"].values():
            if (query_lower in file_data['name'].lower() or 
                query_lower in file_data['caption'].lower()):
                results.append(file_data)
        
        return results
    
    def get_files_by_type(self, file_type: str) -> List[Dict[str, Any]]:
        """Get all files of a specific type"""
        return [file_data for file_data in self.data["files"].values() 
                if file_data['type'] == file_type]
    
    def get_recent_files(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get files uploaded in the last N days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_files = []
        
        for file_data in self.data["files"].values():
            upload_time = datetime.fromisoformat(file_data['upload_time'])
            if upload_time > cutoff_date:
                recent_files.append(file_data)
        
        return recent_files
    
    def cleanup_orphaned_files(self) -> int:
        """Remove files that no longer have associated users"""
        files_to_remove = []
        
        for file_id, file_data in self.data["files"].items():
            user_id = file_data['user_id']
            user_key = str(user_id)
            
            if (user_key not in self.data["users"] or 
                file_id not in self.data["users"][user_key]["files"]):
                files_to_remove.append(file_id)
        
        for file_id in files_to_remove:
            self.delete_file(file_id)
        
        print(f"🧹 Cleaned up {len(files_to_remove)} orphaned files")
        return len(files_to_remove)
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get storage system information"""
        return {
            "storage_file": self.storage_file,
            "file_size": os.path.getsize(self.storage_file) if os.path.exists(self.storage_file) else 0,
            "last_backup": self.last_backup.isoformat() if self.last_backup else None,
            "backup_interval_hours": self.backup_interval,
            "data_created": self.data["settings"]["created_at"],
            "last_modified": self.data["settings"]["last_modified"],
            "version": self.data["settings"]["version"]
        }
    
    def export_data(self, export_file: str = "export.json") -> bool:
        """Export all data to a file"""
        try:
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"📤 Data exported to: {export_file}")
            return True
        except Exception as e:
            print(f"❌ Error exporting data: {e}")
            return False
    
    def import_data(self, import_file: str) -> bool:
        """Import data from a file"""
        try:
            if not os.path.exists(import_file):
                print(f"❌ Import file not found: {import_file}")
                return False
            
            with open(import_file, 'r', encoding='utf-8') as f:
                imported_data = json.load(f)
            
            # Validate imported data structure
            if not all(key in imported_data for key in ["files", "users", "stats", "settings"]):
                print("❌ Invalid data format in import file")
                return False
            
            # Create backup before import
            self._create_backup()
            
            # Replace current data
            self.data = imported_data
            self._save_data()
            
            print(f"📥 Data imported from: {import_file}")
            return True
        except Exception as e:
            print(f"❌ Error importing data: {e}")
            return False
    
    def optimize_storage(self):
        """Optimize storage by removing unused data"""
        original_size = len(self.data["files"])
        
        # Remove orphaned files
        self.cleanup_orphaned_files()
        
        # Remove old daily stats (older than 90 days)
        ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        dates_to_remove = []
        
        for date_str in self.data["stats"]["daily_uploads"]:
            if date_str < ninety_days_ago:
                dates_to_remove.append(date_str)
        
        for date_str in dates_to_remove:
            del self.data["stats"]["daily_uploads"][date_str]
        
        self._save_data()
        
        new_size = len(self.data["files"])
        removed_count = original_size - new_size
        
        print(f"🔧 Storage optimized: removed {removed_count} orphaned files")
        return removed_count

# Test function
def test_storage():
    """Test the storage system"""
    print("🧪 Testing Storage System...")
    
    storage = Storage("test_storage.json")
    
    # Test adding a file
    test_file = {
        'file_id': 'test_file_123',
        'name': 'test_document.pdf',
        'type': 'document',
        'mime_type': 'application/pdf',
        'user_id': 123456,
        'user_name': 'Test User',
        'upload_time': datetime.now().isoformat(),
        'caption': 'This is a test file',
        'file_size': 1024000  # 1MB
                }
    storage.add_file(test_file)
    
    # Test retrieving the file
    retrieved_file = storage.get_file('test_file_123')
    print(f"✅ File retrieved: {retrieved_file['name'] if retrieved_file else 'None'}")
    
    # Test user files
    user_files = storage.get_user_files(123456)
    print(f"✅ User files: {len(user_files)}")
    
    # Test statistics
    stats = storage.get_stats()
    print(f"✅ Total files: {stats['total_files']}")

# Test search
    search_results = storage.search_files(123456, 'test')
    print(f"✅ Search results: {len(search_results)}")
    
    # Clean up test file
    os.remove("test_storage.json")
    print("✅ Storage test completed successfully!")

if __name__ == "__main__":
    test_storage()
