# 📊 Token Usage Tracking

Comprehensive token tracking system for monitoring OpenAI API usage across all operations.

## 🎯 Overview

The Token Tracking system monitors **ALL** OpenAI API calls including:

- **💬 Chat Messages** - User/Assistant conversations
- **🔍 Decision** - LLM decides if Knowledge Graph search is needed
- **📝 Summarization** - Multi-turn conversation summaries
- **🌐 Translation** - Query translation for better search
- **⭐ Importance** - Fact importance scoring

## 🏗️ Architecture

### `TokenTracker` Class (`ui/token_tracker.py`)

Core tracking engine that:
- Records every API call with full metadata
- Calculates costs based on OpenAI pricing
- Provides breakdown by operation type
- Exports data for analysis

### Integration (`ui/streamlit_app.py`)

All OpenAI API calls are wrapped with tracking:

```python
# Example: Chat tracking
completion = client.chat.completions.create(...)
tracker.track_from_response("chat", completion, {
    "turn": turn_number,
    "kg_used": True,
    "facts_count": 5
})
```

## 📊 UI Features

### 1. **Chat Tab - Inline Display**
- Real-time token counter in Memory Configuration section
- Shows: Total Tokens, Input/Output breakdown, Cost
- Updates automatically after each interaction

### 2. **Token Usage Tab - Full Analytics**
- **Overall Metrics**: Total tokens, API calls, cost
- **Breakdown by Operation**: See which operations use most tokens
- **Recent History**: Last 20 API calls with details
- **Cost Projections**: Estimate costs for 100/1000/10000 calls
- **Model Usage**: Track which models are used and their costs

### 3. **Per-Message Display**
- Each chat message shows token usage badge when memories enabled
- Format: `🎫 150 tokens • $0.0002`

## 💰 Cost Calculation

Pricing based on OpenAI rates (as of 2024):

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-4o | $5.00 | $15.00 |
| gpt-4-turbo | $10.00 | $30.00 |
| gpt-3.5-turbo | $0.50 | $1.50 |

**Formula:**
```
Total Cost = (Prompt Tokens × Input Price) + (Completion Tokens × Output Price)
```

## 📈 Usage Examples

### Track Single API Call

```python
from token_tracker import get_tracker

tracker = get_tracker()

# After OpenAI call
response = client.chat.completions.create(...)
tracker.track_from_response("chat", response, {"turn": 1})
```

### Get Statistics

```python
# Total tokens
totals = tracker.get_total_tokens()
# {'prompt_tokens': 1500, 'completion_tokens': 500, 'total_tokens': 2000}

# Total cost
cost = tracker.get_total_cost()
# 0.0012

# Breakdown by operation
breakdown = tracker.get_by_operation()
# {
#   'chat': {'count': 5, 'total_tokens': 1500, 'cost': 0.0010},
#   'decision': {'count': 5, 'total_tokens': 200, 'cost': 0.0001},
#   'summarization': {'count': 2, 'total_tokens': 300, 'cost': 0.0001}
# }
```

### Export Data

```python
# Export to dict
data = tracker.export_to_dict()

# Export to JSON file
tracker.export_to_json("token_usage_20240101.json")
```

## 🔧 Configuration

### Update Pricing

If OpenAI changes pricing, update in `token_tracker.py`:

```python
PRICING = {
    "gpt-4o-mini": {
        "input": 0.00015 / 1000,   # $0.15 per 1M tokens
        "output": 0.0006 / 1000,   # $0.60 per 1M tokens
    },
    # ... other models
}
```

### Track Custom Operations

```python
tracker.track(
    operation="custom_operation",
    model="gpt-4o-mini",
    prompt_tokens=100,
    completion_tokens=50,
    metadata={"custom_field": "value"}
)
```

## 💡 Optimization Tips

Based on tracking data, you can optimize token usage:

### 1. **Reduce Hidden Operations**
- **Problem**: Decision calls on every message
- **Solution**: Use conservative decision mode or manual toggle
- **Savings**: ~30 tokens per message

### 2. **Optimize Summarization**
- **Problem**: Frequent summarization (N=2)
- **Solution**: Increase to N=5 or N=10
- **Savings**: 50% fewer summarization calls

### 3. **Limit Short-term Memory**
- **Problem**: Large context window (20 turns)
- **Solution**: Reduce to 5-10 turns
- **Savings**: ~500 tokens per message

### 4. **Use Cheaper Models**
- **Problem**: Using gpt-4 for all operations
- **Solution**: Use gpt-4o-mini for decision/summarization
- **Savings**: 90% cost reduction for these operations

### 5. **Enable Importance Filtering**
- **Problem**: All facts saved to KG
- **Solution**: Set threshold ≥ 0.3
- **Savings**: ~40% fewer facts ingested

## 📁 Export Format

Exported JSON structure:

```json
{
  "session_start": "2024-10-02T10:00:00",
  "total_calls": 25,
  "total_tokens": {
    "prompt_tokens": 5000,
    "completion_tokens": 2000,
    "total_tokens": 7000
  },
  "total_cost": 0.0042,
  "breakdown_by_operation": {
    "chat": {
      "count": 10,
      "prompt_tokens": 3000,
      "completion_tokens": 1500,
      "total_tokens": 4500,
      "cost": 0.0027
    },
    "decision": {
      "count": 10,
      "prompt_tokens": 500,
      "completion_tokens": 50,
      "total_tokens": 550,
      "cost": 0.0001
    },
    "summarization": {
      "count": 5,
      "prompt_tokens": 1500,
      "completion_tokens": 450,
      "total_tokens": 1950,
      "cost": 0.0014
    }
  },
  "history": [
    {
      "timestamp": "2024-10-02T10:01:00",
      "operation": "chat",
      "model": "gpt-4o-mini",
      "prompt_tokens": 150,
      "completion_tokens": 50,
      "total_tokens": 200,
      "cost": 0.000042,
      "metadata": {
        "turn": 1,
        "kg_used": false
      }
    },
    // ... more records
  ]
}
```

## 🔍 Monitoring Best Practices

### 1. **Regular Review**
- Check Token Usage tab daily/weekly
- Identify high-cost operations
- Adjust settings based on patterns

### 2. **Set Budgets**
- Use cost projections to set monthly budgets
- Monitor avg cost per call
- Alert if exceeding thresholds

### 3. **Compare Models**
- Track which models are most used
- Calculate cost per model
- Switch to cheaper models where appropriate

### 4. **Export for Analysis**
- Export monthly data for reporting
- Analyze trends over time
- Identify optimization opportunities

## 🐛 Troubleshooting

### Issue: Token count seems wrong

**Cause**: OpenAI's tokenizer may differ from estimates

**Solution**: Use actual usage from response object (which we do)

### Issue: Cost calculation doesn't match OpenAI bill

**Cause**: Pricing may have changed or special rates apply

**Solution**: Update PRICING in `token_tracker.py`

### Issue: Some operations not tracked

**Cause**: API call not wrapped with tracker

**Solution**: Find the OpenAI call and add:
```python
tracker.track_from_response("operation_name", response)
```

## 🚀 Future Enhancements

Potential improvements:

- [ ] Rate limiting based on token budget
- [ ] Real-time alerts for high usage
- [ ] Integration with OpenAI usage API
- [ ] Automatic model switching based on budget
- [ ] Token usage predictions (ML-based)
- [ ] Multi-session aggregation
- [ ] Cost optimization recommendations

## 📞 Support

For issues or questions:
1. Check this documentation
2. Review code in `ui/token_tracker.py`
3. Open GitHub issue with details

---

**Last Updated**: October 2024  
**Version**: 1.0.0

