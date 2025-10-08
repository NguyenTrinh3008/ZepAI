# Giải Thích: Tại Sao JSON Search Results Khác Neo4j?

## TL;DR (Too Long; Didn't Read)

**JSON search results chứa RELATIONSHIPS (edges), không phải chỉ ENTITIES (nodes)!**

```
JSON: {name: "WAS_CONVERTED_TO", id: "72a98f51..."}
              ↓
         RELATIONSHIP name
              
Neo4j: Entity {uuid: "72a98f51...", name: "get_user_data()"}
                                            ↓
                                      ENTITY name
```

---

## Chi Tiết

### Vấn Đề Bạn Gặp Phải

```json
// JSON search results
{
  "name": "WAS_CONVERTED_TO",
  "summary": "Converted get_user_data() to async/await",
  "id": "72a98f51-1147-44fe-9dbe-2f9d66f23471"
}
```

```cypher
// Neo4j query
MATCH (e:Entity {id: "72a98f51-1147-44fe-9dbe-2f9d66f23471"})
RETURN e.name
// → No results! ❌
```

### Tại Sao?

1. **JSON `id` field** = Entity UUID (đúng!)
2. **JSON `name` field** = **Relationship name** (không phải entity name!)
3. **Search results** = Relationships + Entities (không phải chỉ entities!)

### Cấu Trúc Thực Tế

```
Graph trong Neo4j:

(get_user_data) --[WAS_CONVERTED_TO]--> (async/await)
       ↓                    ↓                    ↓
  Source Entity      Relationship Name     Target Entity
  UUID: 72a98f51...  Name: WAS_CONVERTED_TO   Name: async/await
  Name: get_user_data()
```

### JSON Search Result Representation

```json
{
  "id": "72a98f51...",         // Source entity UUID
  "name": "WAS_CONVERTED_TO",  // Relationship name
  "summary": "Converted get_user_data() to async/await"  // Full context
}
```

---

## Cách Query Đúng

### ❌ SAI
```cypher
// Tìm entity theo name từ JSON
MATCH (e:Entity {name: "WAS_CONVERTED_TO"})
```

### ✅ ĐÚNG
```cypher
// 1. Tìm entity theo UUID
MATCH (e:Entity {uuid: "72a98f51-1147-44fe-9dbe-2f9d66f23471"})
RETURN e.name
// → "get_user_data()"

// 2. Tìm relationship từ entity
MATCH (source {uuid: "72a98f51..."})-[r]-(target)
WHERE r.name = "WAS_CONVERTED_TO"
RETURN source.name, r.name, target.name
// → get_user_data(), WAS_CONVERTED_TO, async/await
```

---

## Tại Sao Thiết Kế Như Vậy?

**Graphiti search trả về relationships vì chúng có richer semantic context:**

**Query:** `"async await performance refactoring"`

- **Entity only:** `get_user_data()` → không match nhiều keywords
- **Relationship:** `WAS_CONVERTED_TO: Converted get_user_data() to async/await` → match 3/4 keywords!

→ **Relationships rank cao hơn vì có context đầy đủ!**

---

## Quick Reference

| Field | JSON Value | Neo4j Location |
|-------|------------|----------------|
| `id` | `"72a98f51..."` | Entity UUID (`e.uuid`) |
| `name` | `"WAS_CONVERTED_TO"` | Relationship name (`r.name`) |
| `summary` | `"Converted get..."` | Relationship context |

---

## Kết Luận

✅ **Không phải bug** - Đây là feature của knowledge graph!  
✅ **Search đúng** - Results được lấy từ Neo4j qua Graphiti  
✅ **Relationships > Entities** - Vì có semantic context phong phú hơn  

📄 Xem chi tiết: `tests/FINAL_EXPLANATION.md`
