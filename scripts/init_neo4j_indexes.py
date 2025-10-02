# scripts/init_neo4j_indexes.py
"""
Initialize Neo4j indexes for the code memory layer

Run this script after setting up Neo4j to create required indexes.

Usage:
    python scripts/init_neo4j_indexes.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.graph import get_graphiti, create_indexes

async def main():
    """Initialize Neo4j indexes"""
    print("=" * 60)
    print("NEO4J INDEX INITIALIZATION")
    print("=" * 60)
    print()
    
    try:
        print("Connecting to Neo4j...")
        graphiti = await get_graphiti()
        print("✅ Connected to Neo4j")
        print()
        
        print("Creating indexes...")
        print("-" * 60)
        await create_indexes(graphiti)
        print("-" * 60)
        print()
        
        print("✅ Indexes created successfully!")
        print()
        
        # List created indexes
        print("Created indexes:")
        print("  1. entity_project_id - For project isolation queries")
        print("  2. entity_expires_at - For TTL cleanup queries")
        print("  3. entity_file_path - For file-based filtering")
        print("  4. entity_change_type - For change type filtering")
        print()
        
        print("=" * 60)
        print("INITIALIZATION COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
