# 📊 Token Breakdown (Input/Output)

Hiển thị chi tiết **Input (Prompt)** và **Output (Completion)** tokens cho mỗi message.

## 🎯 Feature Overview

Bật **"Show token breakdown (In/Out)"** checkbox để thấy:

### **Before (Simple Mode):**
```
🤖 Assistant: Hello! How can I help?
                    🎫 120 tokens • $0.00007
```

### **After (Breakdown Mode):**
```
🤖 Assistant: Hello! How can I help?
                    🎫 120 tokens • $0.00007
                       ↗️ In: 100 | ↘️ Out: 20
```

---

## 🔧 How to Enable

### **Step 1: Open Chat Tab**

### **Step 2: Find Settings Section**
```
Settings:
├─ Conversation name
├─ Auto-save turns
├─ Show related memories
├─ Pause saving to KG
├─ Mid-term: Ingest every N turns
├─ Short-term: Keep last N turns
└─ ☑️ Show token breakdown (In/Out)  ← CHECK THIS!
```

### **Step 3: Check the Box**
✅ **Show token breakdown (In/Out)**

### **Step 4: See Breakdown on All Messages**
Existing and new messages will show breakdown!

---

## 📊 Understanding the Breakdown

### **↗️ In (Prompt Tokens) = Input to OpenAI**

**What's included:**

#### **1. System Prompt** (~50 tokens)
```
"You are an AI assistant with long-term memory capabilities..."
```
- Fixed content
- Same for all messages
- Defines AI behavior

#### **2. Conversation History** (~100-200 tokens)
```
Last N turns from conversation:
- user: "Hi"
- assistant: "Hello!"
- user: "Tell me about Python"
- assistant: "Python is..."
```
- Dynamic (grows with conversation)
- Limited by short-term window (5/10/20 turns)
- Provides context for AI

#### **3. Retrieved Facts from KG** (~0-150 tokens)
```
"- User learned Python async programming
 - User prefers Python over Java
 - User is working on snake game project"
```
- Only if KG search triggered
- 0-5 facts typically
- ~25-30 tokens per fact

#### **4. Current User Message** (~10-50 tokens)
```
"What did we discuss about Python?"
```
- Varies by message length
- The question/prompt from user

---

### **↘️ Out (Completion Tokens) = Output from OpenAI**

**What's included:**

#### **Assistant's Reply** (~20-200 tokens)
```
"We discussed Python async programming and your snake game project.
Here are the key points..."
```
- The actual response
- Varies by reply length
- Model generates this

---

## 📈 Real Examples

### **Example 1: Simple Message**

```
👤 User: Hi

🤖 Assistant: Hello! How can I help you today?
                    🎫 120 tokens • $0.00007
                       ↗️ In: 100 | ↘️ Out: 20

Breakdown:
├─ In (100):
│  ├─ System prompt: 50
│  ├─ History (empty): 0
│  ├─ KG facts: 0
│  └─ User message "Hi": 10
│  └─ Overhead: 40
│
└─ Out (20):
   └─ Reply "Hello! How...": 20
```

**Analysis:**
- Small message = small tokens
- No history yet (first message)
- No KG search
- Simple reply

---

### **Example 2: Message with History**

```
👤 User: What's async programming?

🤖 Assistant: Async programming allows...
                    🎫 250 tokens • $0.00015
                       ↗️ In: 200 | ↘️ Out: 50

Breakdown:
├─ In (200):
│  ├─ System prompt: 50
│  ├─ History (3 turns): 100
│  ├─ KG facts: 0
│  └─ User message: 50
│
└─ Out (50):
   └─ Reply: 50
```

**Analysis:**
- Larger input due to history
- 3 previous turns added ~100 tokens
- User message longer (~50 tokens)
- Reply moderate length

---

### **Example 3: With KG Search**

```
👤 User: What did we discuss about Python?

🔍 Decision: Query KG → 30 tokens

[📚 Retrieved 3 facts...]

🤖 Assistant: We discussed Python async...
                    🎫 450 tokens • $0.00027
                       ↗️ In: 380 | ↘️ Out: 70

Breakdown:
├─ In (380): ⚠️ High!
│  ├─ System prompt: 50
│  ├─ History (5 turns): 150
│  ├─ KG facts (3): 90  ← Big impact!
│  └─ User message: 90
│
└─ Out (70):
   └─ Reply with context: 70
```

**Analysis:**
- High input due to KG facts
- 3 facts added ~90 tokens
- Longer reply because more context
- **This is expected and good!**

---

### **Example 4: Long Conversation**

```
👤 User: [Message 10 in conversation]

🤖 Assistant: [Reply...]
                    🎫 520 tokens • $0.00031
                       ↗️ In: 430 | ↘️ Out: 90

Breakdown:
├─ In (430): ⚠️ Very high!
│  ├─ System prompt: 50
│  ├─ History (10 turns): 280  ← Growing!
│  ├─ KG facts: 0
│  └─ User message: 100
│
└─ Out (90):
   └─ Reply: 90
```

**Analysis:**
- History is large (10 turns)
- Input tokens growing over time
- This is why we have TTL/summarization!
- Consider: Reduce short-term window

---

## 💡 Optimization Based on Breakdown

### **Pattern 1: High Input, Low Output**

```
🎫 500 tokens • $0.0003
   ↗️ In: 450 | ↘️ Out: 50
```

**Diagnosis:** Lots of context, short reply

**Possible causes:**
- Long conversation history
- Many KG facts
- User message is long

**Solutions:**
- ✅ Reduce short-term window (10 → 5)
- ✅ Limit KG facts (5 → 3)
- ✅ Summarize more often

---

### **Pattern 2: Low Input, High Output**

```
🎫 400 tokens • $0.0024
   ↗️ In: 150 | ↘️ Out: 250
```

**Diagnosis:** Short context, long reply

**Possible causes:**
- AI is being verbose
- Complex explanation needed
- Code generation

**Solutions:**
- ✅ Normal for complex questions!
- ✅ Consider max_tokens limit if too long
- ❌ Don't restrict creativity

---

### **Pattern 3: Balanced**

```
🎫 300 tokens • $0.0018
   ↗️ In: 200 | ↘️ Out: 100
```

**Diagnosis:** Healthy ratio (2:1)

**Analysis:**
- ✅ Good context provided
- ✅ Reasonable reply length
- ✅ Optimal token usage

---

### **Pattern 4: KG Impact**

```
Without KG:
🎫 200 tokens • $0.0012
   ↗️ In: 150 | ↘️ Out: 50

With KG (3 facts):
🎫 380 tokens • $0.0023
   ↗️ In: 310 | ↘️ Out: 70
```

**Analysis:**
- KG added +160 input tokens
- Reply is longer (+20 tokens)
- **Total impact: +180 tokens (+90%)**

**Worth it?**
- ✅ YES if reply is more accurate
- ✅ YES if user needs context
- ❌ NO if facts are irrelevant

---

## 🎯 Cost Implications

### **Input vs Output Pricing (gpt-4o-mini)**

| Type | Price per 1M tokens | Price per token |
|------|-------------------|----------------|
| Input (↗️) | $0.15 | $0.00000015 |
| Output (↘️) | $0.60 | $0.00000060 |

**Output is 4× more expensive than input!**

### **Cost Calculation Examples**

**Example A: High input, low output**
```
In: 400 × $0.00000015 = $0.00006
Out: 50 × $0.00000060 = $0.00003
Total: $0.00009
```

**Example B: Low input, high output**
```
In: 150 × $0.00000015 = $0.000023
Out: 250 × $0.00000060 = $0.00015
Total: $0.000173 (Almost 2× more!)
```

**Key Insight:**
- Reducing output saves more money than reducing input
- But output = value (the reply)
- Focus on optimizing input instead!

---

## 📊 Typical Ratios

### **Good Ratios:**

```
Ratio 2:1 (In:Out)
   ↗️ In: 200 | ↘️ Out: 100
   ✅ Balanced

Ratio 3:1 (In:Out)
   ↗️ In: 300 | ↘️ Out: 100
   ✅ Good context provided

Ratio 4:1 (In:Out)
   ↗️ In: 400 | ↘️ Out: 100
   ⚠️ Lots of context, short reply
```

### **Watch Out For:**

```
Ratio 1:2 (In:Out)
   ↗️ In: 100 | ↘️ Out: 200
   ⚠️ AI being very verbose
   → Consider if this is necessary

Ratio 10:1 (In:Out)
   ↗️ In: 500 | ↘️ Out: 50
   ⚠️ Too much context for short reply
   → Reduce context window
```

---

## 🔍 Debugging with Breakdown

### **Scenario 1: "Why is this message so expensive?"**

**Without breakdown:**
```
🎫 800 tokens • $0.0048
```
❓ "800 tokens seems high..."

**With breakdown:**
```
🎫 800 tokens • $0.0048
   ↗️ In: 650 | ↘️ Out: 150
```
✅ "Ah! 650 input = long history + KG facts"

**Action:** Check history length and KG facts count

---

### **Scenario 2: "Costs increasing over time"**

**Message 1:**
```
🎫 150 tokens
   ↗️ In: 120 | ↘️ Out: 30
```

**Message 5:**
```
🎫 350 tokens
   ↗️ In: 280 | ↘️ Out: 70
```

**Message 10:**
```
🎫 520 tokens
   ↗️ In: 450 | ↘️ Out: 70
```

**Analysis:**
- Input growing: 120 → 280 → 450
- Output stable: 30 → 70 → 70
- **Cause:** Conversation history accumulating
- **Solution:** Reduce window or let TTL work

---

### **Scenario 3: "Comparing with/without KG"**

**Message A (no KG):**
```
🎫 200 tokens
   ↗️ In: 150 | ↘️ Out: 50
```

**Message B (with KG, 3 facts):**
```
🎫 380 tokens
   ↗️ In: 310 | ↘️ Out: 70
```

**Breakdown:**
- Input delta: +160 (KG facts + longer reply needs more context)
- Output delta: +20 (reply has more details)
- **KG impact: +180 tokens total**

**ROI Analysis:**
```
Cost increase: $0.00011 per message
Value: Better, contextual replies
Decision: Worth it for important queries!
```

---

## 🎨 Visual Guide

### **Compact Mode (Default):**
```
🤖 Assistant: [Reply...]
                    🎫 350 tokens • $0.0002
                    📚 3 facts from KG
```

### **Breakdown Mode (Enabled):**
```
🤖 Assistant: [Reply...]
                    🎫 350 tokens • $0.0002
                       ↗️ In: 280 | ↘️ Out: 70
                    📚 3 facts from KG
```

### **Full Context:**
```
🤖 Assistant: We discussed Python async programming and your 
             snake game project. Here are the key points...

                    🎫 450 tokens • $0.00027
                       ↗️ In: 380 | ↘️ Out: 70
                    📚 3 facts from KG

Detailed Breakdown:
├─ INPUT (380 tokens - $0.000057)
│  ├─ System prompt: 50
│  ├─ Conversation history: 150
│  │  └─ Last 5 turns
│  ├─ KG facts: 90
│  │  ├─ Fact 1: "User learned async" (30)
│  │  ├─ Fact 2: "User prefers Python" (30)
│  │  └─ Fact 3: "User building game" (30)
│  └─ User message: 90
│
└─ OUTPUT (70 tokens - $0.000042)
   └─ AI reply: 70
```

---

## 💡 Pro Tips

### **Tip 1: Use Breakdown for Optimization**
```
1. Enable breakdown
2. Chat for 10 messages
3. Review patterns
4. Adjust settings
5. Compare results
```

### **Tip 2: Focus on Input Optimization**
```
Output = Value (the reply)
Input = Cost (context)

→ Optimize input, keep output quality
```

### **Tip 3: KG Facts Sweet Spot**
```
0 facts: No context (-$0.0001)
3 facts: Good context (baseline)
5 facts: Rich context (+$0.00005)
10 facts: Overkill (+$0.00015) ⚠️

→ 3-5 facts is optimal
```

### **Tip 4: Window Size Analysis**
```
Test different window sizes:

Window=3:  Avg In=150
Window=5:  Avg In=200
Window=10: Avg In=300
Window=20: Avg In=450 ⚠️

→ 5-10 is sweet spot
```

---

## 🆘 Troubleshooting

### Issue: Breakdown not showing

**Cause:** Checkbox not enabled

**Fix:** Check ☑️ "Show token breakdown (In/Out)"

### Issue: Old messages don't have breakdown

**Cause:** Only new messages after feature added

**Fix:** Start fresh conversation

### Issue: In/Out don't add up to total

**Cause:** Rounding or display issue

**Fix:** This shouldn't happen - report bug

### Issue: Output tokens very high (>300)

**Cause:** AI being verbose or generating code

**Fix:** 
- Check max_tokens setting
- Review if reply quality justifies length

---

## 📈 Future Enhancements

Potential improvements:

- [ ] Color coding: Green (low) / Yellow (medium) / Red (high)
- [ ] Percentage display: "In: 80% | Out: 20%"
- [ ] Historical chart: Input/Output over time
- [ ] Comparison mode: Compare ratios across messages
- [ ] Budget alerts: Warn if ratio is suboptimal

---

## 📚 Related Documentation

- **[TOKEN_TRACKING.md](TOKEN_TRACKING.md)** - Full token tracking system
- **[PER_MESSAGE_TOKENS.md](PER_MESSAGE_TOKENS.md)** - Per-message display
- **[TOKEN_TRACKING_QUICKSTART.md](TOKEN_TRACKING_QUICKSTART.md)** - Quick start

---

**Last Updated:** October 2024  
**Version:** 2.1.0

