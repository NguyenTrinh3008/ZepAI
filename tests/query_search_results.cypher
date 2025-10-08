// ============================================================================
// CYPHER QUERIES FOR search_results.json
// Copy-paste vào Neo4j Browser để query search results
// ============================================================================

// ----------------------------------------------------------------------------
// 1. VERIFY PROJECT DATA
// ----------------------------------------------------------------------------

// Đếm tổng số entities trong project
MATCH (e:Entity {group_id: 'full_integration_test'})
RETURN count(e) as total_entities;

// Đếm tổng số conversations (Episodic nodes)
MATCH (ep:Episodic {group_id: 'full_integration_test'})
RETURN count(ep) as total_conversations;

// Đếm relationships
MATCH (a {group_id: 'full_integration_test'})-[r]-(b)
RETURN count(r) as total_relationships;


// ----------------------------------------------------------------------------
// 2. QUERY TOP SEARCH RESULTS (từ JSON - Test 1: Async Refactoring)
// ----------------------------------------------------------------------------

// Result 1: WAS_CONVERTED_TO
// UUID: 72a98f51-1147-44fe-9dbe-2f9d66f23471
MATCH (source:Entity {uuid: '72a98f51-1147-44fe-9dbe-2f9d66f23471'})
OPTIONAL MATCH (source)-[r]-(connected)
RETURN 
  source.name as entity_name,
  source.uuid as entity_uuid,
  type(r) as relationship_type,
  r.name as relationship_name,
  connected.name as connected_to
ORDER BY relationship_name
LIMIT 10;

// Result 2: ADDED_INDEX  
// UUID: 3c05a96b-6fc7-468e-92de-2c817de4cc1b
MATCH (source:Entity {uuid: '3c05a96b-6fc7-468e-92de-2c817de4cc1b'})
OPTIONAL MATCH (source)-[r]-(connected)
RETURN 
  source.name as entity_name,
  source.uuid as entity_uuid,
  type(r) as relationship_type,
  r.name as relationship_name,
  connected.name as connected_to
ORDER BY relationship_name
LIMIT 10;

// Result 3: IMPROVED_PERFORMANCE
// UUID: 90c780bc-5023-4c03-95bf-0cfec68b7c05
MATCH (source:Entity {uuid: '90c780bc-5023-4c03-95bf-0cfec68b7c05'})
OPTIONAL MATCH (source)-[r]-(connected)
RETURN 
  source.name as entity_name,
  source.uuid as entity_uuid,
  type(r) as relationship_type,
  r.name as relationship_name,
  connected.name as connected_to
ORDER BY relationship_name
LIMIT 10;


// ----------------------------------------------------------------------------
// 3. TÌM TẤT CẢ ENTITIES TRONG SEARCH RESULTS
// ----------------------------------------------------------------------------

// Tìm tất cả 16 entities có UUIDs trong search results
MATCH (e:Entity)
WHERE e.uuid IN [
  '72a98f51-1147-44fe-9dbe-2f9d66f23471',
  '3c05a96b-6fc7-468e-92de-2c817de4cc1b',
  '90c780bc-5023-4c03-95bf-0cfec68b7c05',
  'e637f638-83c9-43eb-ac51-91ccd681c641',
  '4de39538-3774-481a-988f-f5bad200c581',
  'd96b3412-1f03-4e7b-aeb4-7c7b34984a09',
  '0579f0e1-84d8-4033-8dd7-971fc4563be2',
  '5f40a214-556b-4d6f-897d-992533402856',
  '9c298d14-6149-463c-865f-f8b7d14bbc3d',
  '14d00e86-b20e-474b-adc5-50d162fe1f6c',
  '8b2e6047-fbce-4d18-819b-76cec418d7ac',
  'a853c678-9611-4c80-994b-a8e6529ae5ad',
  '8a982802-950b-43c5-bcd0-964e114899a8',
  '09c537d0-24c9-4ba3-b9f0-4e0e409a91ab',
  '3153a3fe-9ef0-4f69-9f07-5b06d4c053ee',
  '877610cb-ade2-4f6d-9188-cdeb82365679'
]
RETURN 
  e.name as entity_name,
  e.uuid as uuid,
  e.summary as summary,
  labels(e) as labels
ORDER BY e.name;


// ----------------------------------------------------------------------------
// 4. QUERY BY CONVERSATION (request_id)
// ----------------------------------------------------------------------------

// Tìm entities liên quan đến Async Refactoring conversation
MATCH (ep:Episodic {group_id: 'full_integration_test'})
WHERE ep.name CONTAINS 'chat_refactor'
OPTIONAL MATCH (ep)-[r:MENTIONS]-(e:Entity)
RETURN 
  ep.name as conversation,
  collect(DISTINCT e.name) as entities_mentioned
ORDER BY ep.created_at;

// Tìm tất cả conversations và entities
MATCH (ep:Episodic {group_id: 'full_integration_test'})
OPTIONAL MATCH (ep)-[r]-(e:Entity)
RETURN 
  ep.name as conversation,
  count(DISTINCT e) as entity_count,
  collect(DISTINCT e.name)[..5] as sample_entities
ORDER BY ep.created_at;


// ----------------------------------------------------------------------------
// 5. SEMANTIC SEARCH SIMULATION
// ----------------------------------------------------------------------------

// Test 1: Async Refactoring Query
// Query: "async await performance refactoring database"
MATCH (e:Entity {group_id: 'full_integration_test'})
WHERE e.name =~ '(?i).*(async|await|performance|refactor|database).*'
   OR e.summary =~ '(?i).*(async|await|performance|refactor|database).*'
RETURN 
  e.name,
  e.summary,
  e.uuid
ORDER BY e.created_at DESC
LIMIT 10;

// Test 2: Bug Investigation Query
// Query: "keyerror bug user preferences profile error"
MATCH (e:Entity {group_id: 'full_integration_test'})
WHERE e.name =~ '(?i).*(keyerror|bug|user|preferences|profile|error).*'
   OR e.summary =~ '(?i).*(keyerror|bug|user|preferences|profile|error).*'
RETURN 
  e.name,
  e.summary,
  e.uuid
ORDER BY e.created_at DESC
LIMIT 10;

// Test 3: Upload Feature Query
// Query: "upload profile picture image s3 validation"
MATCH (e:Entity {group_id: 'full_integration_test'})
WHERE e.name =~ '(?i).*(upload|profile|picture|image|s3|validation).*'
   OR e.summary =~ '(?i).*(upload|profile|picture|image|s3|validation).*'
RETURN 
  e.name,
  e.summary,
  e.uuid
ORDER BY e.created_at DESC
LIMIT 10;


// ----------------------------------------------------------------------------
// 6. RELATIONSHIP ANALYSIS
// ----------------------------------------------------------------------------

// Tìm tất cả relationship names trong project
MATCH (a {group_id: 'full_integration_test'})-[r]-(b)
WHERE r.name IS NOT NULL
RETURN DISTINCT r.name as relationship_name, count(r) as count
ORDER BY count DESC;

// Tìm relationships với specific names từ search results
MATCH (a {group_id: 'full_integration_test'})-[r]-(b)
WHERE r.name IN [
  'WAS_CONVERTED_TO',
  'ADDED_INDEX',
  'IMPROVED_PERFORMANCE',
  'RAISING_ERROR_AT',
  'FOUND_COUNT_OF',
  'USES_SERVICE',
  'VALIDATES_FILE_TYPE'
]
RETURN 
  a.name as source,
  r.name as relationship,
  b.name as target,
  r.summary as summary
LIMIT 20;


// ----------------------------------------------------------------------------
// 7. FULL CONTEXT FOR SPECIFIC RESULT
// ----------------------------------------------------------------------------

// Lấy full context cho result #1 (Async Refactoring)
MATCH (source:Entity {uuid: '72a98f51-1147-44fe-9dbe-2f9d66f23471'})
OPTIONAL MATCH (source)-[r1:RELATES_TO]-(related)
OPTIONAL MATCH (source)-[r2:MENTIONS]-(conversation)
RETURN 
  source.name as main_entity,
  source.summary as main_summary,
  collect(DISTINCT {
    type: type(r1),
    name: r1.name,
    connected: related.name
  }) as relationships,
  collect(DISTINCT conversation.name) as conversations
LIMIT 1;


// ----------------------------------------------------------------------------
// 8. VERIFY SEARCH RESULTS ACCURACY
// ----------------------------------------------------------------------------

// Check: Có bao nhiêu UUIDs trong search_results.json match với Neo4j?
WITH [
  '72a98f51-1147-44fe-9dbe-2f9d66f23471',
  '3c05a96b-6fc7-468e-92de-2c817de4cc1b',
  '90c780bc-5023-4c03-95bf-0cfec68b7c05',
  'e637f638-83c9-43eb-ac51-91ccd681c641',
  '4de39538-3774-481a-988f-f5bad200c581',
  'd96b3412-1f03-4e7b-aeb4-7c7b34984a09',
  '0579f0e1-84d8-4033-8dd7-971fc4563be2',
  '5f40a214-556b-4d6f-897d-992533402856',
  '9c298d14-6149-463c-865f-f8b7d14bbc3d',
  '14d00e86-b20e-474b-adc5-50d162fe1f6c',
  '8b2e6047-fbce-4d18-819b-76cec418d7ac',
  'a853c678-9611-4c80-994b-a8e6529ae5ad',
  '8a982802-950b-43c5-bcd0-964e114899a8',
  '09c537d0-24c9-4ba3-b9f0-4e0e409a91ab',
  '3153a3fe-9ef0-4f69-9f07-5b06d4c053ee',
  '877610cb-ade2-4f6d-9188-cdeb82365679'
] as search_uuids
MATCH (e:Entity)
WHERE e.uuid IN search_uuids
RETURN 
  size(search_uuids) as total_search_results,
  count(e) as matched_in_neo4j,
  round(count(e) * 100.0 / size(search_uuids)) as match_percentage;


// ----------------------------------------------------------------------------
// 9. EXPLORE CONVERSATION FLOW
// ----------------------------------------------------------------------------

// Xem timeline của conversations theo thứ tự thời gian
MATCH (ep:Episodic {group_id: 'full_integration_test'})
RETURN 
  ep.name as conversation,
  ep.created_at as timestamp
ORDER BY ep.created_at;

// Xem entities được tạo trong mỗi conversation
MATCH (ep:Episodic {group_id: 'full_integration_test'})-[r:MENTIONS]-(e:Entity)
RETURN 
  ep.name as conversation,
  collect(e.name) as entities
ORDER BY ep.created_at;


// ----------------------------------------------------------------------------
// 10. DEBUG QUERIES
// ----------------------------------------------------------------------------

// Xem sample data structure
MATCH (n {group_id: 'full_integration_test'})
RETURN 
  labels(n) as node_type,
  n.name as name,
  n.uuid as uuid,
  keys(n) as available_properties
LIMIT 5;

// Xem tất cả relationship types
MATCH (a {group_id: 'full_integration_test'})-[r]-(b)
RETURN DISTINCT type(r) as relationship_type, count(r) as count
ORDER BY count DESC;

// Xem entities không có relationships
MATCH (e:Entity {group_id: 'full_integration_test'})
WHERE NOT (e)-[]-()
RETURN e.name, e.uuid
LIMIT 10;

