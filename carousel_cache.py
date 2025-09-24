import sqlite3
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import aiosqlite

class CarouselCache:
    """SQLite-based cache for storing carousel data"""
    
    def __init__(self, db_path: str = "carousels.db"):
        self.db_path = db_path
        
    async def init_db(self):
        """Initialize the database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS carousels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    carousel_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    generated_content TEXT NOT NULL,
                    html_content TEXT NOT NULL,
                    public_url TEXT,
                    file_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id INTEGER PRIMARY KEY,
                    session_data TEXT,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_carousel_user_id ON carousels(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_carousel_created_at ON carousels(created_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_carousel_id ON carousels(carousel_id)")
            
            await db.commit()
    
    async def save_carousel(self, carousel_id: str, user_id: int, topic: str, 
                          generated_content: str, html_content: str, 
                          public_url: str = None, file_path: str = None) -> bool:
        """Save a carousel to the cache"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO carousels 
                    (carousel_id, user_id, topic, generated_content, html_content, 
                     public_url, file_path, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (carousel_id, user_id, topic, generated_content, html_content, 
                      public_url, file_path))
                await db.commit()
                return True
        except Exception as e:
            print(f"Error saving carousel to cache: {e}")
            return False
    
    async def get_carousel(self, carousel_id: str) -> Optional[Dict]:
        """Get a carousel by ID"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT * FROM carousels WHERE carousel_id = ?
                """, (carousel_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        columns = [description[0] for description in cursor.description]
                        return dict(zip(columns, row))
                    return None
        except Exception as e:
            print(f"Error getting carousel from cache: {e}")
            return None
    
    async def get_user_carousels(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get recent carousels for a user"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT carousel_id, topic, public_url, created_at 
                    FROM carousels 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (user_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"Error getting user carousels: {e}")
            return []
    
    async def update_carousel_url(self, carousel_id: str, public_url: str, file_path: str) -> bool:
        """Update carousel with published URL and file path"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE carousels 
                    SET public_url = ?, file_path = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE carousel_id = ?
                """, (public_url, file_path, carousel_id))
                await db.commit()
                return True
        except Exception as e:
            print(f"Error updating carousel URL: {e}")
            return False
    
    async def save_user_session(self, user_id: int, session_data: Dict) -> bool:
        """Save user session data"""
        try:
            session_json = json.dumps(session_data)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO user_sessions 
                    (user_id, session_data, last_activity)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (user_id, session_json))
                await db.commit()
                return True
        except Exception as e:
            print(f"Error saving user session: {e}")
            return False
    
    async def get_user_session(self, user_id: int) -> Optional[Dict]:
        """Get user session data"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT session_data FROM user_sessions WHERE user_id = ?
                """, (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        return json.loads(row[0])
                    return None
        except Exception as e:
            print(f"Error getting user session: {e}")
            return None
    
    async def get_carousel_stats(self) -> Dict:
        """Get overall carousel statistics"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Total carousels
                async with db.execute("SELECT COUNT(*) FROM carousels") as cursor:
                    total_carousels = (await cursor.fetchone())[0]
                
                # Unique users
                async with db.execute("SELECT COUNT(DISTINCT user_id) FROM carousels") as cursor:
                    unique_users = (await cursor.fetchone())[0]
                
                # Recent carousels (last 24 hours)
                async with db.execute("""
                    SELECT COUNT(*) FROM carousels 
                    WHERE created_at > datetime('now', '-1 day')
                """) as cursor:
                    recent_carousels = (await cursor.fetchone())[0]
                
                # Most popular topics
                async with db.execute("""
                    SELECT topic, COUNT(*) as count 
                    FROM carousels 
                    GROUP BY LOWER(topic) 
                    ORDER BY count DESC 
                    LIMIT 5
                """) as cursor:
                    popular_topics = await cursor.fetchall()
                
                return {
                    'total_carousels': total_carousels,
                    'unique_users': unique_users,
                    'recent_carousels': recent_carousels,
                    'popular_topics': popular_topics
                }
        except Exception as e:
            print(f"Error getting carousel stats: {e}")
            return {}
    
    async def cleanup_old_sessions(self, days: int = 7) -> int:
        """Clean up old user sessions"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM user_sessions 
                    WHERE last_activity < datetime('now', '-{} days')
                """.format(days))
                deleted_count = cursor.rowcount
                await db.commit()
                return deleted_count
        except Exception as e:
            print(f"Error cleaning up old sessions: {e}")
            return 0
    
    async def search_carousels(self, query: str, user_id: int = None, limit: int = 10) -> List[Dict]:
        """Search carousels by topic or content"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if user_id:
                    sql = """
                        SELECT carousel_id, topic, public_url, created_at 
                        FROM carousels 
                        WHERE user_id = ? AND (
                            topic LIKE ? OR generated_content LIKE ?
                        )
                        ORDER BY created_at DESC 
                        LIMIT ?
                    """
                    params = (user_id, f"%{query}%", f"%{query}%", limit)
                else:
                    sql = """
                        SELECT carousel_id, topic, public_url, created_at 
                        FROM carousels 
                        WHERE topic LIKE ? OR generated_content LIKE ?
                        ORDER BY created_at DESC 
                        LIMIT ?
                    """
                    params = (f"%{query}%", f"%{query}%", limit)
                
                async with db.execute(sql, params) as cursor:
                    rows = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"Error searching carousels: {e}")
            return []
