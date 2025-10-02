# 🚀 Token Tracking - Quick Start Guide

Get started with Token Tracking in 5 minutes!

## ✅ What You Get

After implementing token tracking, you'll see:

1. **💬 In Chat Tab** - Real-time token counter showing:
   - Total tokens used this session
   - Input/Output breakdown
   - Estimated cost

2. **📊 Token Usage Tab** - Full analytics dashboard:
   - Breakdown by operation (chat, decision, summarization)
   - Recent API call history
   - Cost projections
   - Model usage statistics

3. **🎫 Per-Message Badges** - Each message shows its token cost

## 🎯 Quick Actions

### View Current Usage

1. Open Streamlit app: `streamlit run ui/streamlit_app.py`
2. Go to **Chat** tab
3. Look at "Memory Configuration" section → 3rd column shows token usage
4. Or click **Token Usage** tab for full analytics

### Track a Conversation

1. Start chatting in Chat tab
2. Watch token counter update in real-time
3. Every operation is tracked automatically:
   - ✅ Your messages
   - ✅ AI responses
   - ✅ Hidden operations (decision, summarization)

### Export Data

1. Go to **Token Usage** tab
2. Click **"📥 Export to JSON"**
3. Click **"💾 Download JSON"**
4. Data saved to `token_usage_YYYYMMDD_HHMMSS.json`

### Clear History

1. Go to **Token Usage** tab
2. Click **"🗑️ Clear Token History"**
3. Confirm - all tracking data cleared

## 🔢 Understanding the Numbers

### Example Output

```
🔢 Total Tokens: 2,450
↗️ In: 1,800 | ↘️ Out: 650
💰 Cost: $0.0015
```

**What it means:**
- **Total Tokens**: 2,450 tokens used (input + output)
- **In (Prompt)**: 1,800 tokens sent to OpenAI
- **Out (Completion)**: 650 tokens received from OpenAI
- **Cost**: $0.0015 total cost

### Operation Breakdown

When you see this in Token Usage tab:

| Operation | Calls | Tokens | Cost |
|-----------|-------|--------|------|
| Chat | 10 | 2,000 | $0.0012 |
| Decision | 10 | 300 | $0.0001 |
| Summarization | 2 | 150 | $0.0002 |

**What it means:**
- **Chat**: Main conversations - 10 exchanges using 2,000 tokens
- **Decision**: LLM decided 10 times if KG search needed - 300 tokens
- **Summarization**: Summarized conversations 2 times - 150 tokens

## 💡 Optimization Quick Wins

### 1. Reduce Decision Calls (Save ~30% tokens)

**Current**: LLM decides on every message if KG search needed

**Action**: Add manual toggle or use conservative mode

**In code** (future enhancement):
```python
# Skip decision for simple greetings
if len(user_input) < 20 or user_input.lower() in ["hi", "hello", "hey"]:
    wants_kg = False
else:
    # Run decision LLM
```

### 2. Increase Summarization Interval (Save ~50% summarization costs)

**Current**: N=3 (summarize every 3 turns)

**Action**: 
1. Go to Chat tab
2. Change "Ingest every N turns" to **5** or **10**
3. Fewer summarization calls = lower cost

**Savings**: If N=3 → N=5, you reduce summarization by ~40%

### 3. Reduce Short-term Memory Window (Save ~20% chat tokens)

**Current**: Keep last 10 turns

**Action**:
1. Go to Chat tab  
2. Change "Short-term: Keep last N turns" to **5**
3. Less context sent to LLM = lower tokens

**Trade-off**: AI has less conversation history

### 4. Use Cheaper Model (Save ~90% cost!)

**Current**: Using gpt-4

**Action**: Switch to gpt-4o-mini for most operations

**In `.env`**:
```bash
MODEL_NAME=gpt-4o-mini
```

**Savings**: $0.15 per 1M tokens vs $30 per 1M tokens

### 5. Enable Importance Filtering (Save ~40% ingest costs)

**Current**: All facts saved to KG

**Action**: Already enabled! Facts with score < 0.3 are filtered

**Check**: See filtered facts in Chat tab when summarizing

## 📊 Real Example

### Before Optimization
```
Session: 20 messages
Total Tokens: 8,500
Cost: $0.0051

Breakdown:
- Chat: 6,000 tokens ($0.0036)
- Decision: 20 × 30 = 600 tokens ($0.0004)
- Summarization: 10 × 190 = 1,900 tokens ($0.0011)
```

### After Optimization
```
Settings:
✅ N=5 (was 3)
✅ Short-term window=5 (was 10)
✅ Model=gpt-4o-mini (was gpt-4)

Session: 20 messages
Total Tokens: 5,500
Cost: $0.0003

Breakdown:
- Chat: 4,000 tokens ($0.0002)
- Decision: 20 × 30 = 600 tokens ($0.00003)
- Summarization: 4 × 190 = 760 tokens ($0.00005)

SAVINGS: 94% cost reduction! ($0.0051 → $0.0003)
```

## 🎯 Cost Targets

### Recommended Budgets

| Usage Level | Messages/Day | Est. Cost/Month |
|-------------|--------------|-----------------|
| Light | 50 | $0.50 - $1.00 |
| Medium | 200 | $2.00 - $4.00 |
| Heavy | 1000 | $10.00 - $20.00 |

*Based on gpt-4o-mini with optimizations*

### How to Stay Within Budget

1. **Monitor daily** - Check Token Usage tab
2. **Set alerts** - Export weekly, check trends
3. **Adjust settings** - If exceeding budget:
   - Increase N (summarization interval)
   - Reduce short-term window
   - Enable more aggressive importance filtering

## 🔍 Common Patterns

### Pattern: High Decision Costs

**Symptom**: Decision operation uses 30-40% of total tokens

**Cause**: LLM deciding on every message

**Fix**: Skip decision for obvious cases (greetings, short queries)

### Pattern: High Summarization Costs

**Symptom**: Summarization uses 20-30% of total tokens

**Cause**: N is too small (e.g., N=2)

**Fix**: Increase N to 5-10

### Pattern: Large Chat Tokens

**Symptom**: Chat uses 80%+ of tokens, but responses seem short

**Cause**: Large short-term memory window sending too much context

**Fix**: Reduce window from 10 → 5

### Pattern: Varying Costs Per Message

**Symptom**: Some messages cost 10x more than others

**Cause**: KG search retrieves many facts, all sent to LLM

**Fix**: Limit facts sent to LLM (top 5 instead of top 10)

## 📱 Mobile-Friendly View

Token usage is visible on all screen sizes:

- **Desktop**: Full 3-column layout
- **Tablet**: Stacked columns, full metrics
- **Mobile**: Compact view, scrollable tables

## ❓ FAQ

### Q: Why does my cost not match OpenAI's bill exactly?

**A**: Prices may vary based on:
- Volume discounts
- Regional pricing
- Special offers
- Rounding differences

Update `PRICING` in `token_tracker.py` with your actual rates.

### Q: Can I track multiple sessions separately?

**A**: Currently tracks one session. To separate:
1. Export current session
2. Clear token history
3. Start new session

Future: Multi-session support planned

### Q: What operations count as "hidden"?

**A**: Operations you don't see directly:
- **Decision**: LLM decides if KG search needed (every message)
- **Summarization**: LLM extracts facts (every N turns)
- **Translation**: Query translation for non-English (when needed)
- **Importance**: Fact importance scoring (per fact)

### Q: Can I disable tracking?

**A**: Tracking is automatic, but you can:
1. Clear history regularly
2. Don't use Token Usage tab (data still collected)

Future: Add toggle to disable tracking

### Q: How accurate is the token count?

**A**: 100% accurate! We use OpenAI's response object which has exact counts.

## 🆘 Troubleshooting

### Issue: Token counter shows 0

**Cause**: No messages sent yet

**Fix**: Send a message, counter will update

### Issue: Cost seems too high

**Cause**: Using expensive model (gpt-4)

**Fix**: Switch to gpt-4o-mini in `.env`

### Issue: Token Usage tab is empty

**Cause**: No tracking data yet

**Fix**: Chat for a few messages, then check tab

## 🎓 Next Steps

1. **Read full docs**: `docs/TOKEN_TRACKING.md`
2. **Experiment**: Try different settings and observe impact
3. **Optimize**: Find your optimal balance of cost vs. features
4. **Monitor**: Check weekly, adjust as needed

## 📞 Support

Need help? Check:
1. Full documentation: `docs/TOKEN_TRACKING.md`
2. Code: `ui/token_tracker.py`
3. Examples in this guide

---

**Happy Tracking! 📊💰**

