// Fetch Group IDs Query
// Retrieves group_id for nodes that are missing this field

MATCH (n)
WHERE n.uuid IN $uuids
RETURN n.uuid as uuid, n.group_id as group_id
