"""
Dijkstra's Algorithm Visualizer - Streamlit Application
An interactive tool to visualize shortest path finding
"""

import streamlit as st
import time
from typing import List, Dict, Optional, Tuple, Any

from dijkstra import dijkstra, DijkstraResult, parse_matrix_string, validate_matrix
from examples import get_example_graphs, get_example_names, get_example
from graph_visualizer import (
    visualize_graph_matplotlib,
    visualize_graph_plotly,
    create_distance_table
)


# Page configuration
st.set_page_config(
    page_title="Dijkstra's Algorithm Visualizer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        font-weight: 600;
    }
    .result-box {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    .path-display {
        font-size: 1.2em;
        font-weight: bold;
        color: #1f77b4;
    }
    .step-description {
        background-color: #e8f4ea;
        border-left: 4px solid #32CD32;
        padding: 10px 15px;
        margin: 10px 0;
        border-radius: 0 5px 5px 0;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables"""
    if 'matrix' not in st.session_state:
        st.session_state.matrix = None
    if 'labels' not in st.session_state:
        st.session_state.labels = None
    if 'positions' not in st.session_state:
        st.session_state.positions = None
    if 'result' not in st.session_state:
        st.session_state.result = None
    if 'current_step' not in st.session_state:
        st.session_state.current_step = 0
    if 'auto_play' not in st.session_state:
        st.session_state.auto_play = False
    if 'source' not in st.session_state:
        st.session_state.source = 0
    if 'target' not in st.session_state:
        st.session_state.target = 0
    if 'visual_nodes' not in st.session_state:
        st.session_state.visual_nodes = []
    if 'visual_edges' not in st.session_state:
        st.session_state.visual_edges = []


def reset_algorithm():
    """Reset algorithm state"""
    st.session_state.result = None
    st.session_state.current_step = 0
    st.session_state.auto_play = False


def load_example(example_name: str):
    """Load a predefined example"""
    example = get_example(example_name)
    st.session_state.matrix = example['matrix']
    st.session_state.labels = example['labels']
    st.session_state.positions = example.get('positions')
    st.session_state.source = example.get('default_source', 0)
    st.session_state.target = example.get('default_target', len(example['matrix']) - 1)
    reset_algorithm()


def build_matrix_from_visual_editor() -> Tuple[Optional[List[List[float]]], List[str]]:
    """Build adjacency matrix from visual editor state"""
    nodes = st.session_state.visual_nodes
    edges = st.session_state.visual_edges
    
    if not nodes:
        return None, []
    
    n = len(nodes)
    matrix = [[0.0] * n for _ in range(n)]
    labels = [node['label'] for node in nodes]
    
    for edge in edges:
        i, j, weight = edge['from'], edge['to'], edge['weight']
        if 0 <= i < n and 0 <= j < n:
            matrix[i][j] = weight
            matrix[j][i] = weight  # Undirected
    
    return matrix, labels


def render_predefined_examples():
    """Render the predefined examples tab"""
    st.subheader("📚 Predefined Examples")
    
    example_names = get_example_names()
    selected_example = st.selectbox(
        "Choose an example graph:",
        example_names,
        help="Select a predefined graph to visualize"
    )
    
    if selected_example:
        example = get_example(selected_example)
        st.info(example['description'])
        
        if st.button("Load Example", type="primary", use_container_width=True):
            load_example(selected_example)
            st.rerun()


def render_manual_input():
    """Render the manual matrix input tab"""
    st.subheader("📝 Manual Matrix Input")
    
    st.markdown("""
    Enter an adjacency matrix where each row represents connections from a node.
    - Use **0** for no connection
    - Use positive numbers for edge weights
    - Rows should be comma or space separated
    """)
    
    # Node count
    num_nodes = st.number_input(
        "Number of nodes:",
        min_value=2,
        max_value=20,
        value=5,
        help="Number of nodes in the graph"
    )
    
    # Generate template
    template = "\n".join([", ".join(["0"] * num_nodes) for _ in range(num_nodes)])
    
    matrix_input = st.text_area(
        "Adjacency Matrix:",
        value=template,
        height=200,
        help="Enter the adjacency matrix (comma or space separated)"
    )
    
    # Node labels
    labels_input = st.text_input(
        "Node Labels (comma separated, optional):",
        value=", ".join([str(i) for i in range(num_nodes)]),
        help="Custom labels for nodes"
    )
    
    if st.button("Parse Matrix", type="primary", use_container_width=True):
        matrix, error = parse_matrix_string(matrix_input)
        
        if matrix:
            labels = [l.strip() for l in labels_input.split(',')] if labels_input else None
            if labels and len(labels) != len(matrix):
                st.warning(f"Number of labels ({len(labels)}) doesn't match matrix size ({len(matrix)}). Using default labels.")
                labels = [str(i) for i in range(len(matrix))]
            
            st.session_state.matrix = matrix
            st.session_state.labels = labels
            st.session_state.positions = None
            st.session_state.source = 0
            st.session_state.target = len(matrix) - 1
            reset_algorithm()
            st.success("Matrix loaded successfully!")
            st.rerun()
        else:
            st.error(f"Error: {error}")


def render_visual_editor():
    """Render the visual graph editor tab"""
    st.subheader("🎨 Visual Graph Editor")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("**Add Nodes**")
        new_node_label = st.text_input("Node Label:", value=f"N{len(st.session_state.visual_nodes)}")
        
        if st.button("Add Node", use_container_width=True):
            # Add node with auto-positioning
            n = len(st.session_state.visual_nodes)
            import math
            angle = 2 * math.pi * n / max(1, n + 1)
            x = 1 + 0.8 * math.cos(angle)
            y = 1 + 0.8 * math.sin(angle)
            
            st.session_state.visual_nodes.append({
                'id': n,
                'label': new_node_label,
                'x': x,
                'y': y
            })
            st.rerun()
    
    with col2:
        st.markdown("**Add Edges**")
        nodes = st.session_state.visual_nodes
        
        if len(nodes) >= 2:
            node_options = {f"{n['label']} ({n['id']})": n['id'] for n in nodes}
            
            from_node = st.selectbox("From:", list(node_options.keys()), key="edge_from")
            to_node = st.selectbox("To:", list(node_options.keys()), key="edge_to")
            weight = st.number_input("Weight:", min_value=0.1, value=1.0, step=0.1)
            
            if st.button("Add Edge", use_container_width=True):
                from_id = node_options[from_node]
                to_id = node_options[to_node]
                
                if from_id != to_id:
                    st.session_state.visual_edges.append({
                        'from': from_id,
                        'to': to_id,
                        'weight': weight
                    })
                    st.rerun()
                else:
                    st.warning("Cannot add self-loop!")
        else:
            st.info("Add at least 2 nodes first")
    
    # Display current nodes and edges
    st.markdown("---")
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("**Current Nodes:**")
        for i, node in enumerate(st.session_state.visual_nodes):
            cols = st.columns([3, 1])
            cols[0].write(f"• {node['label']} (ID: {node['id']})")
            if cols[1].button("🗑️", key=f"del_node_{i}"):
                # Remove node and related edges
                node_id = node['id']
                st.session_state.visual_nodes = [n for n in st.session_state.visual_nodes if n['id'] != node_id]
                st.session_state.visual_edges = [e for e in st.session_state.visual_edges 
                                                  if e['from'] != node_id and e['to'] != node_id]
                # Re-index nodes
                for idx, n in enumerate(st.session_state.visual_nodes):
                    n['id'] = idx
                # Update edge references
                st.rerun()
    
    with col4:
        st.markdown("**Current Edges:**")
        for i, edge in enumerate(st.session_state.visual_edges):
            nodes = st.session_state.visual_nodes
            from_label = nodes[edge['from']]['label'] if edge['from'] < len(nodes) else '?'
            to_label = nodes[edge['to']]['label'] if edge['to'] < len(nodes) else '?'
            
            cols = st.columns([3, 1])
            cols[0].write(f"• {from_label} → {to_label} (w: {edge['weight']})")
            if cols[1].button("🗑️", key=f"del_edge_{i}"):
                st.session_state.visual_edges.pop(i)
                st.rerun()
    
    # Build and use button
    st.markdown("---")
    col5, col6 = st.columns(2)
    
    with col5:
        if st.button("Build Graph", type="primary", use_container_width=True):
            matrix, labels = build_matrix_from_visual_editor()
            if matrix and len(matrix) >= 2:
                st.session_state.matrix = matrix
                st.session_state.labels = labels
                positions = {node['id']: (node['x'], node['y']) for node in st.session_state.visual_nodes}
                st.session_state.positions = positions
                st.session_state.source = 0
                st.session_state.target = len(matrix) - 1
                reset_algorithm()
                st.success("Graph built successfully!")
                st.rerun()
            else:
                st.error("Need at least 2 nodes to build a graph!")
    
    with col6:
        if st.button("Clear All", type="secondary", use_container_width=True):
            st.session_state.visual_nodes = []
            st.session_state.visual_edges = []
            st.rerun()


def render_algorithm_controls():
    """Render algorithm controls"""
    if st.session_state.matrix is None:
        st.info("👆 Load a graph using one of the input methods in the sidebar")
        return
    
    matrix = st.session_state.matrix
    labels = st.session_state.labels
    n = len(matrix)
    
    st.subheader("⚙️ Algorithm Controls")
    
    col1, col2 = st.columns(2)
    
    with col1:
        node_options = [labels[i] if labels and i < len(labels) else str(i) for i in range(n)]
        source_idx = st.selectbox(
            "Source Node:",
            range(n),
            format_func=lambda x: node_options[x],
            index=min(st.session_state.source, n - 1)
        )
        st.session_state.source = source_idx
    
    with col2:
        target_idx = st.selectbox(
            "Target Node:",
            range(n),
            format_func=lambda x: node_options[x],
            index=min(st.session_state.target, n - 1)
        )
        st.session_state.target = target_idx
    
    col3, col4, col5 = st.columns(3)
    
    with col3:
        if st.button("🚀 Run Algorithm", type="primary", use_container_width=True):
            result = dijkstra(matrix, source_idx, labels)
            st.session_state.result = result
            st.session_state.current_step = 0
            st.rerun()
    
    with col4:
        if st.button("🔄 Reset", use_container_width=True):
            reset_algorithm()
            st.rerun()
    
    with col5:
        if st.session_state.result:
            auto = st.checkbox("Auto-play", value=st.session_state.auto_play)
            st.session_state.auto_play = auto


def render_step_controls():
    """Render step-through controls"""
    if st.session_state.result is None:
        return
    
    result = st.session_state.result
    total_steps = len(result.steps)
    current = st.session_state.current_step
    
    st.markdown("---")
    st.subheader("📊 Step-through Visualization")
    
    # Step slider
    step = st.slider(
        "Step:",
        0, total_steps - 1,
        value=current,
        key="step_slider"
    )
    st.session_state.current_step = step
    
    # Step controls
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("⏮️ First", use_container_width=True):
            st.session_state.current_step = 0
            st.rerun()
    
    with col2:
        if st.button("◀️ Previous", use_container_width=True, disabled=(current <= 0)):
            st.session_state.current_step = max(0, current - 1)
            st.rerun()
    
    with col3:
        if st.button("Next ▶️", use_container_width=True, disabled=(current >= total_steps - 1)):
            st.session_state.current_step = min(total_steps - 1, current + 1)
            st.rerun()
    
    with col4:
        if st.button("Last ⏭️", use_container_width=True):
            st.session_state.current_step = total_steps - 1
            st.rerun()
    
    # Auto-play
    if st.session_state.auto_play and current < total_steps - 1:
        time.sleep(0.8)
        st.session_state.current_step = current + 1
        st.rerun()
    
    # Current step description
    current_step_data = result.steps[step]
    st.markdown(f"""
    <div class="step-description">
        <strong>Step {step + 1}/{total_steps}:</strong> {current_step_data.description}
    </div>
    """, unsafe_allow_html=True)


def render_visualization():
    """Render the main graph visualization"""
    if st.session_state.matrix is None:
        return
    
    matrix = st.session_state.matrix
    labels = st.session_state.labels
    positions = st.session_state.positions
    source = st.session_state.source
    target = st.session_state.target
    
    # Determine visualization state
    visited = None
    current_node = None
    path = None
    
    if st.session_state.result:
        result = st.session_state.result
        step = st.session_state.current_step
        step_data = result.steps[step]
        
        visited = step_data.visited
        current_node = step_data.current_node if step_data.current_node >= 0 else None
        
        # Show path on final step
        if step == len(result.steps) - 1:
            path = result.get_path(target)
    
    # Render graph
    st.subheader("🔍 Graph Visualization")
    
    # Use Plotly for interactivity
    fig = visualize_graph_plotly(
        matrix=matrix,
        labels=labels,
        positions=positions,
        visited=visited,
        current_node=current_node,
        path=path,
        source=source,
        target=target,
        title="Dijkstra's Algorithm Visualization"
    )
    
    st.plotly_chart(fig, width='stretch')


def render_results():
    """Render algorithm results"""
    if st.session_state.result is None:
        return
    
    result = st.session_state.result
    labels = st.session_state.labels
    target = st.session_state.target
    
    st.markdown("---")
    st.subheader("📋 Results")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Shortest path
        path = result.get_path(target)
        distance = result.get_distance(target)
        
        st.markdown("**Shortest Path:**")
        if path:
            path_labels = [labels[i] if labels and i < len(labels) else str(i) for i in path]
            path_str = " → ".join(path_labels)
            st.markdown(f'<p class="path-display">{path_str}</p>', unsafe_allow_html=True)
            st.metric("Total Distance", f"{distance:.1f}")
        else:
            st.warning("No path exists to the target node!")
    
    with col2:
        # Distance table
        st.markdown("**Distance Table:**")
        table_data = create_distance_table(result.distances, labels, result.source)
        st.dataframe(table_data, width='stretch', hide_index=True)


def render_matrix_display():
    """Display the current adjacency matrix"""
    if st.session_state.matrix is None:
        return
    
    with st.expander("📊 View Adjacency Matrix"):
        matrix = st.session_state.matrix
        labels = st.session_state.labels
        
        import pandas as pd
        
        col_labels = [labels[i] if labels and i < len(labels) else str(i) for i in range(len(matrix))]
        df = pd.DataFrame(matrix, columns=col_labels, index=col_labels)
        st.dataframe(df, width='stretch')


def main():
    """Main application"""
    initialize_session_state()
    
    # Header
    st.title("🔍 Dijkstra's Algorithm Visualizer")
    st.markdown("An interactive tool to visualize shortest path finding using Dijkstra's algorithm")
    
    # Sidebar
    with st.sidebar:
        st.header("📥 Input Method")
        
        tabs = st.tabs(["Examples", "Manual", "Editor"])
        
        with tabs[0]:
            render_predefined_examples()
        
        with tabs[1]:
            render_manual_input()
        
        with tabs[2]:
            render_visual_editor()
    
    # Main content
    render_algorithm_controls()
    render_step_controls()
    render_visualization()
    render_results()
    render_matrix_display()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #888;">
        <small>
            Dijkstra's Algorithm Visualizer | 
            Built with Streamlit, NetworkX & Plotly
        </small>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
