import os
import asyncpg
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

async def save_leads(leads: List[Dict]):
    """将采集到的线索批量存入数据库的 leads 表中"""
    if not leads:
        return
    
    # URL format: postgresql://postgres:openclaw@localhost:5432/openclaw_db
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:openclaw@localhost:5432/openclaw_db")
    
    try:
        conn = await asyncpg.connect(database_url)
    except Exception as e:
        print(f"[DB Error] Cannot connect to database: {e}")
        return
    try:
        # PostgreSQL 的 executemany 批量插入语法
        query = """
            INSERT INTO leads (platform, username, profile_url, email, followers, tags)
            VALUES ($1, $2, $3, $4, $5, $6)
        """
        values = []
        for lead in leads:
            values.append((
                lead.get('platform', ''),
                lead.get('username', ''),
                lead.get('profile_url', ''),
                lead.get('email', None),
                lead.get('followers', 0),
                lead.get('tags', [])
            ))
        
        await conn.executemany(query, values)
        print(f"[DB] Successfully saved {len(leads)} leads to the database.")
    except Exception as e:
        print(f"[DB Error] Failed to save leads: {e}")
    finally:
        await conn.close()
