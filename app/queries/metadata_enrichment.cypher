// Metadata Enrichment Query
// Fetches comprehensive metadata for search results including:
// - Code change metadata (file, changes, language, etc.)
// - Conversation metadata (chat, model, tokens, etc.)
// - Related nodes (CodeChange, ContextFile, ToolCall)

MATCH (n)
WHERE n.uuid IN $uuids

// Find related nodes - traverse up to 3 hops for CodeChange/Request
OPTIONAL MATCH path1 = (n)-[*1..3]-(codeChange:CodeChange)
WHERE codeChange.group_id = n.group_id

OPTIONAL MATCH path2 = (n)-[*1..3]-(request:Request)
WHERE request.group_id = n.group_id OR request.project_id = n.group_id

OPTIONAL MATCH (n)-[*1..2]-(contextFile:ContextFile)
WHERE contextFile.group_id = n.group_id

OPTIONAL MATCH (n)-[*1..2]-(toolCall:ToolCall)
WHERE toolCall.group_id = n.group_id

// Collect all related nodes
WITH n, 
     collect(DISTINCT codeChange) as codeChanges,
     collect(DISTINCT request) as requests,
     collect(DISTINCT contextFile) as contextFiles,
     collect(DISTINCT toolCall) as toolCalls

// Get first non-null CodeChange/Request for metadata (prefer closest)
WITH n, codeChanges, requests, contextFiles, toolCalls,
     CASE WHEN size(codeChanges) > 0 THEN codeChanges[0] ELSE null END as firstCodeChange,
     CASE WHEN size(requests) > 0 THEN requests[0] ELSE null END as firstRequest

RETURN n.uuid as uuid,
       n.name as name,
       n.summary as summary,
       n.episode_body as episode_body,
       labels(n) as labels,
       
       // Code change metadata - MERGE from n or related CodeChange
       COALESCE(n.file_path, firstCodeChange.file_path) as file_path,
       COALESCE(n.change_type, firstCodeChange.change_type) as change_type,
       COALESCE(n.severity, firstCodeChange.severity) as severity,
       COALESCE(n.lines_added, firstCodeChange.lines_added) as lines_added,
       COALESCE(n.lines_removed, firstCodeChange.lines_removed) as lines_removed,
       COALESCE(n.imports, firstCodeChange.imports) as imports,
       COALESCE(n.function_name, firstCodeChange.function_name) as function_name,
       COALESCE(n.change_summary, firstCodeChange.change_summary, firstCodeChange.summary) as change_summary,
       COALESCE(n.language, firstCodeChange.language) as language,
       COALESCE(n.diff_summary, firstCodeChange.diff_summary) as diff_summary,
       
       // Conversation metadata - MERGE from n or related Request
       COALESCE(n.project_id, firstRequest.project_id, n.group_id) as project_id,
       COALESCE(n.request_id, firstRequest.request_id) as request_id,
       COALESCE(n.chat_id, firstRequest.chat_id) as chat_id,
       COALESCE(n.chat_mode, firstRequest.chat_mode) as chat_mode,
       COALESCE(n.model, firstRequest.model) as model,
       COALESCE(n.total_tokens, firstRequest.total_tokens) as total_tokens,
       COALESCE(n.message_count, firstRequest.message_count) as message_count,
       COALESCE(n.context_file_count, firstRequest.context_file_count) as context_file_count,
       COALESCE(n.tool_call_count, firstRequest.tool_call_count) as tool_call_count,
       
       // Related nodes detailed info
       [node IN codeChanges WHERE node IS NOT NULL | {
         type: 'CodeChange',
         uuid: node.uuid,
         name: node.name,
         file_path: node.file_path,
         change_type: node.change_type,
         severity: node.severity,
         lines_added: node.lines_added,
         lines_removed: node.lines_removed,
         change_summary: node.change_summary
       }] +
       [node IN contextFiles WHERE node IS NOT NULL | {
         type: 'ContextFile',
         uuid: node.uuid,
         name: node.name,
         file_path: node.file_path,
         usefulness_score: node.usefulness_score
       }] +
       [node IN toolCalls WHERE node IS NOT NULL | {
         type: 'ToolCall',
         uuid: node.uuid,
         name: node.name,
         tool_name: node.tool_name
       }] as related_nodes
