# ui/graphiti_token_ui.py
"""
Streamlit UI Components for Graphiti Token Tracking

Hiển thị token usage chi tiết cho Graphiti operations.
"""

import streamlit as st
from typing import Optional, Dict, Any
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graphiti_token_tracker import GraphitiTokenTracker, get_global_tracker


def get_graphiti_tracker():
    """Get Graphiti token data from API server"""
    import requests
    import os
    
    api_base = os.getenv("MEMORY_LAYER_API", "http://127.0.0.1:8000")
    
    try:
        # Fetch stats from API
        response = requests.get(f"{api_base}/graphiti/tokens/stats", timeout=5)
        response.raise_for_status()
        stats = response.json()
        
        # Fetch operations breakdown
        ops_response = requests.get(f"{api_base}/graphiti/tokens/operations", timeout=5)
        ops_response.raise_for_status()
        operations = ops_response.json()
        
        # Fetch full export for history
        export_response = requests.get(f"{api_base}/graphiti/tokens/export", timeout=5)
        export_response.raise_for_status()
        export_data = export_response.json()
        
        # Return combined data
        return {
            "stats": stats,
            "operations": operations,
            "history": export_data.get("history", []),
            "from_api": True
        }
        
    except Exception as e:
        st.warning(f"⚠️ Could not fetch Graphiti token data from API: {e}")
        return None


def display_graphiti_overview(data: dict):
    """Display overall Graphiti token statistics"""
    if not data:
        return
        
    stats = data.get('stats', {})
    
    if stats.get('total_calls', 0) == 0:
        st.info("ℹ️ No Graphiti operations tracked yet. Start by adding episodes to see token usage.")
        return
    
    st.markdown("### 📊 Graphiti Pipeline Overview")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Episodes",
            f"{stats['unique_episodes']}",
            help="Number of episodes processed through Graphiti"
        )
    
    with col2:
        st.metric(
            "LLM Calls",
            f"{stats['total_calls']:,}",
            help="Total number of LLM calls made by Graphiti"
        )
    
    with col3:
        st.metric(
            "Total Tokens",
            f"{stats['total_tokens']:,}",
            help="Total tokens used across all operations"
        )
    
    with col4:
        st.metric(
            "Total Cost",
            f"${stats['total_cost']:.4f}",
            help="Total cost in USD"
        )
    
    # Averages
    st.markdown("#### 📈 Averages")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        avg_per_episode = stats['avg_tokens_per_episode']
        st.metric(
            "Tokens/Episode",
            f"{avg_per_episode:,.0f}",
            help="Average tokens per episode"
        )
    
    with col2:
        avg_per_call = stats['avg_tokens_per_call']
        st.metric(
            "Tokens/Call",
            f"{avg_per_call:,.0f}",
            help="Average tokens per LLM call"
        )
    
    with col3:
        avg_cost = stats['total_cost'] / stats['unique_episodes'] if stats['unique_episodes'] > 0 else 0
        st.metric(
            "Cost/Episode",
            f"${avg_cost:.6f}",
            help="Average cost per episode"
        )


def display_operation_breakdown(data: dict):
    """Display breakdown by Graphiti operation type"""
    if not data:
        return
        
    breakdown = data.get('operations', {})
    
    if not breakdown:
        st.info("No operation data available")
        return
    
    st.markdown("### 🔬 Token Usage by Graphiti Operation")
    
    # Sort by total tokens (descending)
    sorted_ops = sorted(breakdown.items(), key=lambda x: x[1]['total_tokens'], reverse=True)
    
    # Create table data
    table_data = []
    total_tokens = sum(data['total_tokens'] for _, data in breakdown.items())
    
    for op, data in sorted_ops:
        pct = (data['total_tokens'] / total_tokens * 100) if total_tokens > 0 else 0
        
        # Format operation name
        op_display = op.replace('_', ' ').title()
        if op.startswith('graphiti_'):
            op_display = op_display.replace('Graphiti ', '')
        
        table_data.append({
            "Operation": op_display,
            "Calls": data['count'],
            "Total Tokens": f"{data['total_tokens']:,}",
            "Avg/Call": f"{data['avg_tokens_per_call']:.0f}",
            "% of Total": f"{pct:.1f}%",
            "Cost": f"${data['cost']:.6f}"
        })
    
    st.dataframe(table_data, use_container_width=True, hide_index=True)
    
    # Visual breakdown - pie chart
    st.markdown("#### 📊 Visual Breakdown")
    
    import pandas as pd
    
    # Prepare data for chart
    chart_data = pd.DataFrame([
        {"Operation": op.replace('_', ' ').title(), "Tokens": data['total_tokens']}
        for op, data in sorted_ops
    ])
    
    st.bar_chart(chart_data.set_index("Operation"))


def display_episode_details(tracker: GraphitiTokenTracker):
    """Display details for individual episodes"""
    # Get all episodes
    episodes = {}
    for usage in tracker.usage_history:
        if usage.episode_id:
            if usage.episode_id not in episodes:
                episodes[usage.episode_id] = []
            episodes[usage.episode_id].append(usage)
    
    if not episodes:
        st.info("No episode data available")
        return
    
    st.markdown("### 📝 Episode Details")
    
    # Select episode
    episode_ids = sorted(episodes.keys(), reverse=True)  # Most recent first
    selected_episode = st.selectbox(
        "Select Episode",
        options=episode_ids,
        format_func=lambda x: f"{x[:20]}..." if len(x) > 20 else x,
        key="graphiti_episode_selector"
    )
    
    if selected_episode:
        # Get episode stats
        stats = tracker.get_episode_summary(selected_episode)
        
        st.markdown(f"#### Episode: `{selected_episode}`")
        
        # Key metrics for this episode
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("LLM Calls", stats['call_count'])
        
        with col2:
            st.metric("Total Tokens", f"{stats['total_tokens']:,}")
        
        with col3:
            st.metric("Cost", f"${stats['total_cost']:.6f}")
        
        with col4:
            avg_per_call = stats['total_tokens'] / stats['call_count'] if stats['call_count'] > 0 else 0
            st.metric("Avg/Call", f"{avg_per_call:.0f}")
        
        # Operation breakdown for this episode
        st.markdown("##### Operations in this Episode")
        
        ep_ops_data = []
        for op, data in stats['operations'].items():
            op_display = op.replace('_', ' ').title()
            ep_ops_data.append({
                "Operation": op_display,
                "Calls": data['count'],
                "Tokens": f"{data['total_tokens']:,}",
                "Cost": f"${data['cost']:.6f}"
            })
        
        st.dataframe(ep_ops_data, use_container_width=True, hide_index=True)


def display_cost_projections(tracker: GraphitiTokenTracker):
    """Display cost projections and optimization tips"""
    stats = tracker.get_total_stats()
    
    if stats['unique_episodes'] == 0:
        return
    
    st.markdown("### 💰 Cost Projections")
    
    avg_cost_per_episode = stats['total_cost'] / stats['unique_episodes']
    
    # Projections
    projections = {
        "100 episodes": 100,
        "1,000 episodes": 1000,
        "10,000 episodes": 10000,
        "100,000 episodes": 100000
    }
    
    proj_data = []
    for label, count in projections.items():
        cost = avg_cost_per_episode * count
        proj_data.append({
            "Scale": label,
            "Projected Cost": f"${cost:.2f}",
            "Cost per Episode": f"${avg_cost_per_episode:.6f}"
        })
    
    st.dataframe(proj_data, use_container_width=True, hide_index=True)
    
    # Optimization recommendations
    st.markdown("### 💡 Optimization Recommendations")
    
    breakdown = tracker.get_operation_breakdown()
    
    if breakdown:
        # Find most expensive operation
        sorted_ops = sorted(breakdown.items(), key=lambda x: x[1]['total_tokens'], reverse=True)
        most_expensive = sorted_ops[0]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"""
            **🎯 Focus Area:**
            
            The `{most_expensive[0].replace('_', ' ')}` operation uses the most tokens:
            - **{most_expensive[1]['total_tokens']:,}** tokens ({most_expensive[1]['total_tokens']/stats['total_tokens']*100:.1f}% of total)
            - **{most_expensive[1]['count']}** calls
            - **${most_expensive[1]['cost']:.4f}** cost
            
            Consider optimizing this operation first.
            """)
        
        with col2:
            st.success("""
            **✅ Optimization Tips:**
            
            1. **Use gpt-4o-mini** instead of gpt-4 (8x cheaper)
            2. **Truncate long episodes** before processing
            3. **Tune similarity thresholds** to reduce resolution calls
            4. **Batch similar episodes** when possible
            5. **Monitor resolution rate** - if >80%, adjust thresholds
            """)


def display_recent_calls(tracker: GraphitiTokenTracker, limit: int = 20):
    """Display recent LLM calls"""
    recent = tracker.get_recent(limit)
    
    if not recent:
        st.info("No recent calls")
        return
    
    st.markdown("### 📜 Recent LLM Calls")
    
    call_data = []
    for usage in reversed(recent):  # Most recent first
        op_display = usage.operation.replace('_', ' ').title()
        episode_short = usage.episode_id[:12] + "..." if usage.episode_id and len(usage.episode_id) > 12 else (usage.episode_id or "N/A")
        
        call_data.append({
            "Time": usage.timestamp.split("T")[1][:8],  # HH:MM:SS
            "Operation": op_display,
            "Episode": episode_short,
            "Model": usage.model.split("-")[-1] if "-" in usage.model else usage.model,
            "Tokens": f"{usage.total_tokens}",
            "Cost": f"${usage.cost:.6f}"
        })
    
    st.dataframe(call_data, use_container_width=True, hide_index=True)


def display_export_options(tracker: GraphitiTokenTracker):
    """Display export options for Graphiti token data"""
    st.markdown("### 📥 Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📄 Export JSON Report", key="export_graphiti_json"):
            import json
            
            data = tracker.export_to_dict()
            json_str = json.dumps(data, indent=2)
            
            st.download_button(
                label="💾 Download JSON",
                data=json_str,
                file_name=f"graphiti_token_report_{data['session_start'][:10]}.json",
                mime="application/json"
            )
            
            st.success("✅ JSON report ready for download")
    
    with col2:
        if st.button("📊 Export Text Summary", key="export_graphiti_text"):
            summary = tracker.get_summary_text()
            
            st.download_button(
                label="💾 Download Text",
                data=summary,
                file_name=f"graphiti_token_summary_{tracker.session_start[:10]}.txt",
                mime="text/plain"
            )
            
            st.success("✅ Text summary ready for download")
    
    # Show summary preview
    with st.expander("📋 Preview Summary", expanded=False):
        st.text(tracker.get_summary_text())


def render_graphiti_token_tab():
    """Main render function for Graphiti token tracking tab"""
    st.subheader("🔬 Graphiti Token Usage (Estimated)")
    
    st.markdown("""
    Track **estimated** token usage and costs for Graphiti's knowledge graph pipeline.
    Graphiti uses LLM in multiple steps: entity extraction, resolution, fact extraction, etc.
    
    **Note:** Token counts are estimates based on content analysis (~85-95% accurate).
    """)
    
    # Fetch data from API
    data = get_graphiti_tracker()
    
    # Check if there's any data
    if not data or data.get('stats', {}).get('total_calls', 0) == 0:
        st.info("""
        ℹ️ **No Graphiti operations tracked yet.**
        
        To start tracking:
        1. Process episodes via `/ingest/text` or `/ingest/message` endpoints
        2. Token usage will be estimated automatically
        3. Return here to see analytics
        
        **Quick test:**
        ```bash
        curl -X POST http://127.0.0.1:8000/ingest/text \\
          -H "Content-Type: application/json" \\
          -d '{"name":"test","text":"User likes Python.","source_description":"test","group_id":"test"}'
        ```
        """)
        return
    
    # Display components
    display_graphiti_overview(data)
    
    st.markdown("---")
    
    display_operation_breakdown(data)
    
    st.markdown("---")
    
    # Show API data indicator
    if data.get('from_api'):
        st.caption("📡 Data fetched from API server")
    
    # Tabs for detailed views (simplified since we're using API data)
    detail_tabs = st.tabs(["📊 Summary", "🎯 Entities", "💰 Projections"])
    
    with detail_tabs[0]:
        # Summary view
        st.markdown("### 📊 Token Usage Summary")
        
        stats = data.get('stats', {})
        st.json(stats)
        
        st.markdown("### 🔬 Operations Breakdown")
        operations = data.get('operations', {})
        st.json(operations)
    
    with detail_tabs[1]:
        # Entity statistics
        display_entity_statistics()
    
    with detail_tabs[2]:
        # Cost projections
        st.markdown("### 💰 Cost Projections")
        
        stats = data.get('stats', {})
        unique_episodes = stats.get('unique_episodes', 0)
        total_cost = stats.get('total_cost', 0)
        
        if unique_episodes > 0:
            avg_cost = total_cost / unique_episodes
            
            projections = {
                "100 episodes": 100,
                "1,000 episodes": 1000,
                "10,000 episodes": 10000,
                "100,000 episodes": 100000
            }
            
            proj_data = []
            for label, count in projections.items():
                cost = avg_cost * count
                proj_data.append({
                    "Scale": label,
                    "Projected Cost": f"${cost:.2f}",
                    "Cost per Episode": f"${avg_cost:.6f}"
                })
            
            st.dataframe(proj_data, use_container_width=True, hide_index=True)
        else:
            st.info("No episode data yet for projections")
    
    # Refresh button
    st.markdown("---")
    if st.button("🔄 Refresh Data", key="refresh_graphiti_data"):
        st.rerun()


def display_entity_statistics():
    """Display entity statistics from Neo4j"""
    import requests
    import os
    
    st.markdown("### 🎯 Entity Statistics")
    
    st.markdown("""
    Entities are the nodes created by Graphiti from your episodes.
    Each entity represents a person, concept, or thing mentioned in conversations.
    """)
    
    api_base = os.getenv("MEMORY_LAYER_API", "http://127.0.0.1:8000")
    
    try:
        response = requests.get(f"{api_base}/graphiti/entities/stats", timeout=10)
        response.raise_for_status()
        entity_data = response.json()
        
        # Overall stats
        total_stats = entity_data.get('total_stats', {})
        
        if total_stats:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Total Entities",
                    f"{total_stats.get('total_entities', 0):,}",
                    help="Total number of entities created by Graphiti"
                )
            
            with col2:
                st.metric(
                    "Unique Groups",
                    f"{total_stats.get('unique_groups', 0):,}",
                    help="Number of different conversation groups"
                )
            
            with col3:
                st.metric(
                    "Unique Names",
                    f"{total_stats.get('unique_entity_names', 0):,}",
                    help="Number of distinct entity names"
                )
            
            # Entities by group
            st.markdown("#### 📦 Entities by Group/Conversation")
            by_group = entity_data.get('by_group', [])
            
            if by_group:
                group_data = []
                for item in by_group:
                    group_id = item['group_id']
                    group_short = group_id[:20] + "..." if len(group_id) > 20 else group_id
                    group_data.append({
                        "Group ID": group_short,
                        "Entity Count": item['entity_count']
                    })
                
                st.dataframe(group_data, use_container_width=True, hide_index=True)
            else:
                st.info("No group data available")
            
            # Most connected entities
            st.markdown("#### 🔗 Most Connected Entities")
            st.caption("Entities with the most relationships to other entities")
            
            most_connected = entity_data.get('most_connected', [])
            
            if most_connected:
                connected_data = []
                for item in most_connected:
                    connected_data.append({
                        "Entity": item['entity'],
                        "Relationships": item['relationships']
                    })
                
                st.dataframe(connected_data, use_container_width=True, hide_index=True)
            else:
                st.info("No relationship data available")
            
            # Recent entities
            with st.expander("📋 Recently Created Entities", expanded=False):
                top_entities = entity_data.get('top_entities', [])
                
                if top_entities:
                    for entity in top_entities[:10]:
                        st.markdown(f"**{entity['name']}**")
                        if entity.get('summary'):
                            st.caption(entity['summary'])
                        st.caption(f"Group: {entity['group_id'][:20]}... | Created: {entity.get('created_at', 'N/A')[:10]}")
                        st.markdown("---")
                else:
                    st.info("No entities found")
        else:
            st.warning("No entity statistics available")
            
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Could not fetch entity statistics: {e}")
        st.info("Make sure the API server is running and Neo4j is accessible.")


# Helper function for compact display (can be used in other tabs)
def display_graphiti_compact_metrics(tracker_or_data):
    """Display compact Graphiti metrics (for sidebar or info panel)"""
    import requests
    import os
    
    # Fetch from API
    try:
        api_base = os.getenv("MEMORY_LAYER_API", "http://127.0.0.1:8000")
        response = requests.get(f"{api_base}/graphiti/tokens/stats", timeout=2)
        response.raise_for_status()
        stats = response.json()
        
        if stats.get('total_calls', 0) == 0:
            st.caption("🔬 No Graphiti data")
            return
        
        st.caption(f"""
        🔬 **Graphiti Pipeline (Est.)**
        - Episodes: {stats.get('unique_episodes', 0)}
        - LLM Calls: {stats.get('total_calls', 0):,}
        - Tokens: {stats.get('total_tokens', 0):,}
        - Cost: ${stats.get('total_cost', 0):.4f}
        """)
    except:
        st.caption("🔬 Graphiti: N/A")


if __name__ == "__main__":
    # For testing
    st.set_page_config(page_title="Graphiti Token Tracking", layout="wide")
    render_graphiti_token_tab()

