// Create Required Indexes for Graphiti
// Run this in Neo4j Browser after resetting database

// 1. Create fulltext index for node search (REQUIRED by Graphiti)
CREATE FULLTEXT INDEX node_name_and_summary IF NOT EXISTS
FOR (n:Entity|Episodic)
ON EACH [n.name, n.summary, n.content];

// 2. Create fulltext index for edge search
CREATE FULLTEXT INDEX edge_name_and_fact IF NOT EXISTS  
FOR ()-[r:RELATES_TO]-()
ON EACH [r.name, r.fact];

// 3. Create range indexes for performance
CREATE INDEX entity_created_at IF NOT EXISTS FOR (n:Entity) ON (n.created_at);
CREATE INDEX entity_group_id IF NOT EXISTS FOR (n:Entity) ON (n.group_id);
CREATE INDEX episodic_created_at IF NOT EXISTS FOR (n:Episodic) ON (n.created_at);
CREATE INDEX episodic_group_id IF NOT EXISTS FOR (n:Episodic) ON (n.group_id);

// 4. Create vector index for embeddings
CREATE VECTOR INDEX entity_name_embedding IF NOT EXISTS
FOR (n:Entity) ON (n.name_embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};

// 5. Verify indexes created
SHOW INDEXES;
