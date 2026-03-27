"""
Caregiver Console page for Dementia Chatbot (custom router version)
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from config import SessionKeys, SUPPORTED_LANGUAGES


def render_caregiver_console():
    """Render the caregiver console"""
    st.markdown("### 👥 Caregiver Console")
    
    components = st.session_state.get('components', {})
    if not components:
        st.error("System components not initialized")
        return
    
    memory_system = components['memory_system']
    db = components['db']
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "✅ Memory Review", "📈 Activity Log", "🔧 Management"])
    
    with tab1:
        render_dashboard(memory_system, db)
    with tab2:
        render_memory_review(memory_system, db)
    with tab3:
        render_activity_log(db)
    with tab4:
        render_management_tools(memory_system, db)


def render_dashboard(memory_system, db):
    st.markdown("#### 📊 System Dashboard")
    try:
        stats = memory_system.get_memory_stats()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Memories", stats['total_memories'])
        with col2:
            verified_count = stats['trust_levels'].get('trusted', 0)
            unverified_count = stats['trust_levels'].get('unverified', 0)
            total_count = verified_count + unverified_count
            verification_rate = (verified_count / total_count * 100) if total_count > 0 else 0
            st.metric("Verification Rate", f"{verification_rate:.1f}%")
        with col3:
            st.metric("Pending Review", unverified_count)
        with col4:
            recent_activity = len(db.get_activity_log(limit=100))
            st.metric("Recent Activity", recent_activity)
        col1, col2 = st.columns(2)
        with col1:
            if stats['languages']:
                st.markdown("##### Memories by Language")
                lang_data = pd.DataFrame(list(stats['languages'].items()), columns=['Language', 'Count'])
                lang_data['Language'] = lang_data['Language'].map(lambda x: SUPPORTED_LANGUAGES.get(x, x))
                st.bar_chart(lang_data.set_index('Language'))
        with col2:
            if stats['sources']:
                st.markdown("##### Memories by Source")
                source_data = pd.DataFrame(list(stats['sources'].items()), columns=['Source', 'Count'])
                st.bar_chart(source_data.set_index('Source'))
        if stats['trust_levels']:
            st.markdown("##### Trust Level Distribution")
            trust_data = pd.DataFrame(list(stats['trust_levels'].items()), columns=['Trust Level', 'Count'])
            col1, col2 = st.columns(2)
            with col1:
                st.bar_chart(trust_data.set_index('Trust Level'))
            with col2:
                st.markdown("**Trust Level Breakdown:**")
                for level, count in stats['trust_levels'].items():
                    percentage = (count / stats['total_memories'] * 100) if stats['total_memories'] > 0 else 0
                    st.write(f"• {level.title()}: {count} ({percentage:.1f}%)")
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")


def render_memory_review(memory_system, db):
    st.markdown("#### ✅ Memory Review")
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_language = st.selectbox(
            "Filter by Language:",
            options=["All"] + list(SUPPORTED_LANGUAGES.keys()),
            format_func=lambda x: "All" if x == "All" else SUPPORTED_LANGUAGES[x]
        )
    with col2:
        filter_trust = st.selectbox(
            "Filter by Trust Level:",
            options=["All", "unverified", "trusted", "flagged"]
        )
    with col3:
        filter_source = st.selectbox(
            "Filter by Source:",
            options=["All", "voice", "text", "imported"]
        )
    try:
        memories = db.get_all_memories()
        if filter_language != "All":
            memories = [m for m in memories if m['language'] == filter_language]
        if filter_trust != "All":
            memories = [m for m in memories if m['trust_level'] == filter_trust]
        if filter_source != "All":
            memories = [m for m in memories if m['source'] == filter_source]
        st.markdown(f"**Found {len(memories)} memories**")
        if memories:
            for i, memory in enumerate(memories):
                with st.container():
                    st.markdown(f"---")
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**Memory {i+1}:** {memory['text']}")
                        st.caption(f"Added: {memory['created_at']} • Source: {memory['source']} • Language: {SUPPORTED_LANGUAGES.get(memory['language'], memory['language'])}")
                        if memory['tags']:
                            st.write("**Tags:**", ", ".join(memory['tags']))
                    with col2:
                        if memory['trust_level'] == 'trusted':
                            st.success("✓ Verified")
                        elif memory['trust_level'] == 'unverified':
                            st.warning("⏳ Pending")
                        else:
                            st.info(memory['trust_level'])
                        col_verify, col_flag, col_delete = st.columns(3)
                        with col_verify:
                            if memory['trust_level'] != 'trusted':
                                if st.button("✓", key=f"verify_{memory['id']}", help="Verify this memory"):
                                    memory_system.db.update_memory_trust_level(memory['id'], "trusted", True)
                                    db.log_activity("caregiver", "verified_memory", memory['id'])
                                    st.success("Memory verified!")
                                    st.rerun()
                        with col_flag:
                            if memory['trust_level'] != 'flagged':
                                if st.button("⚠️", key=f"flag_{memory['id']}", help="Flag this memory"):
                                    memory_system.db.update_memory_trust_level(memory['id'], "flagged", True)
                                    db.log_activity("caregiver", "flagged_memory", memory['id'])
                                    st.warning("Memory flagged!")
                                    st.rerun()
                        with col_delete:
                            if st.button("🗑️", key=f"delete_{memory['id']}", help="Delete this memory"):
                                memory_system.delete_memory(memory['id'])
                                db.log_activity("caregiver", "deleted_memory", memory['id'])
                                st.error("Memory deleted!")
                                st.rerun()
        else:
            st.info("No memories found matching the selected filters.")
    except Exception as e:
        st.error(f"Error loading memories: {e}")


def render_activity_log(db):
    st.markdown("#### 📈 Activity Log")
    col1, col2 = st.columns(2)
    with col1:
        log_limit = st.selectbox("Show last N entries:", [50, 100, 200, 500])
    with col2:
        filter_user = st.selectbox("Filter by user:", ["All", "user", "caregiver"])
    try:
        activities = db.get_activity_log(limit=log_limit) if filter_user == "All" else db.get_activity_log(filter_user, limit=log_limit)
        if activities:
            for activity in activities:
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.write(f"**{activity['action']}**")
                        if activity['details']:
                            st.caption(activity['details'])
                    with col2:
                        st.write(activity['user_id'])
                    with col3:
                        st.caption(activity['timestamp'])
                    st.markdown("---")
        else:
            st.info("No activity log entries found.")
    except Exception as e:
        st.error(f"Error loading activity log: {e}")


def render_management_tools(memory_system, db):
    st.markdown("#### 🔧 Management Tools")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Rebuild Memory Index", use_container_width=True):
            with st.spinner("Rebuilding memory index..."):
                try:
                    memory_system.rebuild_index()
                    st.success("Memory index rebuilt successfully!")
                except Exception as e:
                    st.error(f"Error rebuilding index: {e}")
    with col2:
        if st.button("🧹 Clear Activity Log", use_container_width=True):
            if st.checkbox("Confirm clearing activity log"):
                st.success("Activity log cleared!")


