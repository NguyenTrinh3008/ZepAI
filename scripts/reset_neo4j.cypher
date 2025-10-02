// ============================================================================
// COMPLETE NEO4J RESET - Run each command ONE BY ONE in Neo4j Browser
// ============================================================================

// STEP 1: Drop all constraints first (constraints own some indexes)
DROP CONSTRAINT entity_uuid_unique IF EXISTS;
DROP CONSTRAINT episodic_uuid_unique IF EXISTS;

// STEP 2: Drop all custom indexes
DROP INDEX node_name_and_summary IF EXISTS;
DROP INDEX edge_name_and_fact IF EXISTS;
DROP INDEX entity_created_at IF EXISTS;
DROP INDEX entity_group_id IF EXISTS;
DROP INDEX episodic_created_at IF EXISTS;
DROP INDEX episodic_group_id IF EXISTS;
DROP INDEX entity_name_embedding IF EXISTS;
DROP INDEX entity_uuid_unique IF EXISTS;

// STEP 3: Delete all data
MATCH (n) DETACH DELETE n;

// 4. Verify empty
MATCH (n) RETURN count(n) as total_nodes;
// Should return 0

// 5. Show indexes (should be empty)
SHOW INDEXES;

// 6. Show constraints (should be empty)
SHOW CONSTRAINTS;
