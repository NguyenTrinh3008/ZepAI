#!/usr/bin/env python3
"""
Check actual entity names in Neo4j
"""

import os
import asyncio
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv

load_dotenv()

async def check_actual_entities():
    """Check what entity names actually exist in Neo4j"""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    try:
        async with driver.session() as session:
            print("🔍 Checking actual entity names in Neo4j")
            print("="*50)
            
            # Get all entities in the project
            query = """
            MATCH (e:Entity {group_id: 'full_integration_test'})
            RETURN e.name, e.id, e.created_at
            ORDER BY e.name
            """
            result = await session.run(query)
            entities = await result.data()
            
            print(f"📊 Found {len(entities)} entities in project 'full_integration_test'")
            print()
            
            # Show all entity names
            print("📋 All entity names:")
            for i, entity in enumerate(entities, 1):
                name = entity['e.name']
                entity_id = entity['e.id']
                created = entity['e.created_at']
                print(f"{i:3d}. {name}")
                print(f"     ID: {entity_id}")
                print(f"     Created: {created}")
                print()
            
            # Check for patterns
            print("\n🔍 Analyzing entity name patterns:")
            patterns = {}
            for entity in entities:
                name = entity['e.name']
                if '_' in name:
                    prefix = name.split('_')[0]
                    patterns[prefix] = patterns.get(prefix, 0) + 1
            
            print("Common prefixes:")
            for prefix, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
                print(f"   • {prefix}_* : {count} entities")
            
            # Check for specific patterns from JSON
            json_patterns = ['WAS_CONVERTED_TO', 'ADDED_INDEX', 'IMPROVED_PERFORMANCE', 'SECURITY_ISSUE']
            print(f"\n🔍 Checking for JSON patterns:")
            for pattern in json_patterns:
                matches = [e for e in entities if pattern.lower() in e['e.name'].lower() or pattern in e['e.name']]
                if matches:
                    print(f"   ✅ '{pattern}' found in:")
                    for match in matches[:3]:
                        print(f"      • {match['e.name']}")
                else:
                    print(f"   ❌ '{pattern}' not found")
            
            # Check Episodic nodes
            print(f"\n💬 Episodic nodes:")
            episodic_query = """
            MATCH (ep:Episodic {group_id: 'full_integration_test'})
            RETURN ep.name, ep.id, ep.created_at
            ORDER BY ep.created_at
            """
            episodic_result = await session.run(episodic_query)
            episodic_nodes = await episodic_result.data()
            
            for i, ep in enumerate(episodic_nodes, 1):
                name = ep['ep.name'] or "Unnamed"
                ep_id = ep['ep.id'] or "No ID"
                created = ep['ep.created_at']
                print(f"{i}. {name}")
                print(f"   ID: {ep_id}")
                print(f"   Created: {created}")
                print()
                
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(check_actual_entities())
