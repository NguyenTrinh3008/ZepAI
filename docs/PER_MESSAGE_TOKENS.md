# 💬 Per-Message Token Display

Hiển thị chi tiết token usage cho **từng message riêng biệt** và **hidden operations** (summarization, decision).

## 🎯 Overview

Hệ thống giờ đây hiển thị:

1. **💬 Token Badge cho mỗi Assistant Message** - Biết chính xác message nào tốn bao nhiêu tokens
2. **📝 Summarization Notifications** - Khi AI tóm tắt conversations, hiện token usage
3. **🔍 Decision Tokens** (Optional) - Hidden operation khi AI quyết định query KG

## 📊 Display Format

### **1. Per-Message Token Badge**

Mỗi assistant message sẽ hiển thị:

```
🤖 Assistant:
[Message content here...]

                    🎫 250 tokens • $0.0002
                    📚 5 facts from KG
```

**Thông tin hiển thị:**
- `🎫` Token count và cost
- `📚` Số facts được retrieve từ Knowledge Graph (nếu có)

### **2. Summarization Notification**

Khi AI tóm tắt N turns, hiện box thông báo:

```
ℹ️ 📝 AI Summarized 5 turns

   🎫 180 tokens • $0.0001

   Model: gpt-4o-mini
```

**Khi nào hiển thị:**
- Chỉ khi "Show related memories" checkbox được bật
- Sau mỗi N turns (ví dụ: N=5)
- Trước khi ingest facts vào KG

### **3. Decision Tokens** (Debug Mode)

Khi AI quyết định có cần query KG không:

```
🔍 Decision: Query KG → 30 tokens
```

**Khi nào hiển thị:**
- Chỉ khi "Show related memories" checkbox được bật
- Chỉ khi decision = YES (cần query KG)
- Hiện ở phía trên retrieved memories

## 🎨 Visual Examples

### **Example 1: Simple Chat (No KG)**

```
👤 User: Hello!

🤖 Assistant: Hi there! How can I help?
                    🎫 120 tokens • $0.00007
```

**Breakdown:**
- User message: No tokens (không gọi API)
- Assistant message: 120 tokens
  - Prompt: ~100 (history + system prompt)
  - Completion: ~20 (reply)

### **Example 2: Chat with KG Search**

```
👤 User: What did we talk about Python?

🔍 Decision: Query KG → 30 tokens

[Related memories shown here...]

🤖 Assistant: We discussed Python async programming...
                    🎫 350 tokens • $0.0002
                    📚 3 facts from KG
```

**Breakdown:**
- Decision: 30 tokens (LLM decides to query KG)
- Chat: 350 tokens
  - Prompt: ~280 (history + system + 3 facts)
  - Completion: ~70 (longer reply with context)

### **Example 3: Summarization Event**

```
👤 User: [Message 5]

🤖 Assistant: [Reply to message 5]
                    🎫 200 tokens • $0.0001

ℹ️ 📝 AI Summarized 5 turns

   🎫 180 tokens • $0.0001

   Model: gpt-4o-mini

📝 Ingesting 3 facts to Knowledge Graph...
✓ Ingested fact 1/3 (score: 0.8)
⚠️ Filtered low-importance fact: ... (score: 0.2)
✓ Ingested fact 2/3 (score: 0.7)
```

**Breakdown:**
- Message 5 reply: 200 tokens
- Summarization: 180 tokens
  - Prompt: ~150 (last 5 turns to summarize)
  - Completion: ~30 (extracted facts)
- Total for this exchange: 380 tokens

### **Example 4: Full Conversation View**

```
Chat History:

👤 User: Hi

🤖 Assistant: Hello!
                    🎫 100 tokens • $0.00006

👤 User: Tell me about async

🤖 Assistant: Async programming allows...
                    🎫 250 tokens • $0.00015

👤 User: Give example

🤖 Assistant: Here's an async example...
                    🎫 450 tokens • $0.00027
                    📚 2 facts from KG

👤 User: Thanks

🤖 Assistant: You're welcome!
                    🎫 110 tokens • $0.00007

ℹ️ 📝 AI Summarized 3 turns

   🎫 180 tokens • $0.0001

   Model: gpt-4o-mini

Total This Chat: 1,090 tokens • $0.00065
```

## 📈 Token Composition

### **What's Included in Each Message's Token Count?**

**Assistant Message Tokens = Prompt + Completion**

**Prompt Tokens Include:**
1. System prompt
2. Short-term conversation history (last N turns)
3. Retrieved facts from KG (if any)
4. Current user message

**Completion Tokens Include:**
1. Assistant's reply

**Example Breakdown for 350 token message:**
```
Prompt: 280 tokens
  - System prompt: 50 tokens
  - Last 5 turns history: 150 tokens
  - 3 facts from KG: 60 tokens
  - Current user message: 20 tokens

Completion: 70 tokens
  - Assistant reply: 70 tokens

Total: 350 tokens
```

## 🔍 Understanding Token Patterns

### **Pattern 1: Increasing Tokens Over Time**

```
Message 1: 150 tokens
Message 2: 200 tokens
Message 3: 250 tokens
Message 4: 300 tokens
```

**Cause:** Short-term memory window keeps growing
- Each message adds to history
- More history = more prompt tokens

**Solution:** Conversation auto-resets or reduce window size

### **Pattern 2: Spike on KG Retrieval**

```
Message 1: 150 tokens (no KG)
Message 2: 400 tokens (with KG, 5 facts)
Message 3: 180 tokens (no KG)
```

**Cause:** Message 2 retrieved 5 facts from KG
- Each fact adds ~50 tokens to prompt
- 5 facts = +250 tokens

**Solution:** Normal behavior, shows KG is working

### **Pattern 3: Summarization Every N Turns**

```
Turn 1-2: Chat messages (300 tokens total)
Turn 3-4: Chat messages (320 tokens total)
Turn 5: Chat message (160 tokens)
        + Summarization (180 tokens)
Total for Turn 5: 340 tokens
```

**Cause:** N=5 setting triggers summarization
- Every 5 user messages → summarize
- Summarization is separate API call

**Solution:** Increase N to reduce summarization frequency

## 💡 Optimization Tips Based on Per-Message Data

### **Tip 1: Identify High-Token Messages**

Look at your chat history and find messages with high tokens:

```
Message A: 150 tokens ✅ Normal
Message B: 800 tokens ⚠️ High!
Message C: 200 tokens ✅ Normal
```

**Why is Message B high?**
- Check if "📚 X facts from KG" is shown → KG added context
- Check if it's a long reply → Natural
- Check if history is long → Consider reducing window

### **Tip 2: Monitor Summarization Cost**

If you see many summarization notifications:

```
Turn 3: Summarization (180 tokens)
Turn 6: Summarization (190 tokens)
Turn 9: Summarization (185 tokens)
```

**Cost:** 555 tokens just for summarization
**Solution:** Increase N from 3 → 5 or 10

### **Tip 3: Compare With/Without KG**

```
Without KG: 150-200 tokens per message
With KG: 300-400 tokens per message
```

**Insight:** KG adds ~150 tokens on average
**Worth it?** Yes if replies are more contextual!

### **Tip 4: Check Model Consistency**

All messages should use same model:

```
Message 1: gpt-4o-mini ✅
Message 2: gpt-4o-mini ✅
Summarization: gpt-4o-mini ✅
```

If you see gpt-4 unexpectedly → Check .env MODEL_NAME

## 🎯 Use Cases

### **Use Case 1: Debug High Costs**

**Problem:** Monthly bill higher than expected

**Solution:**
1. Review chat history
2. Find high-token messages
3. Check if KG retrieval is excessive
4. Adjust settings (reduce window, increase N)

### **Use Case 2: Optimize for Speed**

**Problem:** Replies take too long

**Solution:**
1. Check per-message tokens
2. High tokens = slower API calls
3. Reduce short-term window
4. Disable KG for simple queries

### **Use Case 3: Cost Transparency**

**Problem:** Users want to know their usage

**Solution:**
- Per-message tokens show exact usage
- Users can see what actions cost tokens
- Transparency builds trust

### **Use Case 4: A/B Testing**

**Scenario:** Test different settings

**Test A:** N=3, Window=10
```
Avg per message: 300 tokens
Summarization every 3 turns: 180 tokens
```

**Test B:** N=5, Window=5
```
Avg per message: 200 tokens
Summarization every 5 turns: 180 tokens
```

**Winner:** Test B (33% fewer tokens!)

## 🛠️ Technical Details

### **Data Structure**

Each message stored with token_usage:

```python
{
    "role": "assistant",
    "content": "Hello! How can I help?",
    "token_usage": {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
        "cost": 0.000072,
        "model": "gpt-4o-mini",
        "kg_used": False,
        "facts_count": 0
    }
}
```

### **User Messages**

User messages have `token_usage: None` because:
- No API call made for user input
- Tokens only counted when LLM responds
- User input tokens are part of next assistant message's prompt

### **Display Logic**

```python
# Only show for assistant messages
if msg["role"] == "assistant" and msg.get("token_usage"):
    usage = msg["token_usage"]
    st.caption(f"🎫 {usage['total_tokens']:,} tokens • ${usage['cost']:.4f}")
    
    # Show KG usage if applicable
    if usage.get('kg_used'):
        st.caption(f"📚 {usage['facts_count']} facts from KG")
```

## 📊 Expected Token Ranges

### **Typical Ranges:**

| Message Type | Token Range | Notes |
|--------------|-------------|-------|
| Simple reply (no KG) | 100-200 | Short history |
| Normal reply (no KG) | 200-350 | Medium history |
| Reply with KG (3-5 facts) | 300-500 | KG context added |
| Long reply with KG | 500-800 | Many facts + long reply |
| Summarization | 150-250 | Depends on N turns |
| Decision | 20-40 | Very small |

### **Red Flags:**

⚠️ **> 1000 tokens per message** - Check:
- Short-term window too large?
- Too many KG facts retrieved?
- Very long system prompt?

⚠️ **Summarization > 300 tokens** - Check:
- N too large? (summarizing 10+ turns)
- Long conversation turns?

⚠️ **Decision > 50 tokens** - Should be small, check prompt

## 🎓 Best Practices

### **1. Monitor Regularly**

- Check per-message tokens weekly
- Identify patterns
- Adjust settings as needed

### **2. Set Expectations**

Tell users:
- Simple questions: ~150 tokens
- Questions needing memory: ~300 tokens
- Long conversations accumulate

### **3. Use Filters Wisely**

- Enable KG only when needed
- Adjust N based on conversation depth
- Balance cost vs. quality

### **4. Export for Analysis**

- Token Usage tab → Export JSON
- Analyze patterns offline
- Create reports

## 🆘 Troubleshooting

### Issue: Tokens not showing on messages

**Cause:** Old messages from before feature added

**Fix:** Only new messages will show tokens

### Issue: All messages show same token count

**Cause:** Bug or caching issue

**Fix:** Clear conversation and start fresh

### Issue: Summarization notification doesn't appear

**Cause:** "Show related memories" is unchecked

**Fix:** Enable checkbox in Chat tab

### Issue: Token badges misaligned

**Cause:** Long message content

**Fix:** Normal behavior, badges align to right

## 📈 Future Enhancements

Potential additions:

- [ ] Token usage chart per conversation
- [ ] Highlight most expensive messages
- [ ] Token budget warnings per message
- [ ] Export per-message data to CSV
- [ ] Compare token usage across conversations

---

**Last Updated:** October 2024  
**Version:** 2.0.0

