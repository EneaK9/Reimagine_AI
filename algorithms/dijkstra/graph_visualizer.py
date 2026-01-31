"""
Graph Visualization Module for Dijkstra's Algorithm
Uses NetworkX and Matplotlib/Plotly for rendering
"""

import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
from typing import List, Dict, Tuple, Optional, Set, Any
import plotly.graph_objects as go


def create_networkx_graph(
    matrix: List[List[float]], 
    labels: Optional[List[str]] = None,
    directed: bool = False
) -> nx.Graph:
    """
    Create a NetworkX graph from an adjacency matrix
    
    Args:
        matrix: Adjacency matrix
        labels: Node labels (optional)
        directed: Whether the graph is directed
    
    Returns:
        NetworkX Graph or DiGraph
    """
    n = len(matrix)
    
    if directed:
        G = nx.DiGraph()
    else:
        G = nx.Graph()
    
    # Add nodes with labels
    for i in range(n):
        label = labels[i] if labels and i < len(labels) else str(i)
        G.add_node(i, label=label)
    
    # Add edges with weights
    for i in range(n):
        for j in range(n):
            if matrix[i][j] > 0 and matrix[i][j] != float('inf'):
                if directed or i < j:  # For undirected, only add each edge once
                    G.add_edge(i, j, weight=matrix[i][j])
                elif not directed and i > j and matrix[j][i] == 0:
                    # Handle asymmetric undirected case
                    G.add_edge(i, j, weight=matrix[i][j])
    
    return G


def is_directed_graph(matrix: List[List[float]]) -> bool:
    """Check if a matrix represents a directed graph"""
    n = len(matrix)
    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] != matrix[j][i]:
                return True
    return False


def visualize_graph_matplotlib(
    matrix: List[List[float]],
    labels: Optional[List[str]] = None,
    positions: Optional[Dict[int, Tuple[float, float]]] = None,
    visited: Optional[Set[int]] = None,
    current_node: Optional[int] = None,
    path: Optional[List[int]] = None,
    source: Optional[int] = None,
    target: Optional[int] = None,
    figsize: Tuple[int, int] = (10, 8),
    title: str = "Graph Visualization"
) -> Figure:
    """
    Visualize a graph using Matplotlib
    
    Args:
        matrix: Adjacency matrix
        labels: Node labels
        positions: Node positions {node_id: (x, y)}
        visited: Set of visited nodes (highlighted in green)
        current_node: Currently processing node (highlighted in yellow)
        path: List of nodes in the shortest path (highlighted edges)
        source: Source node (highlighted in blue)
        target: Target node (highlighted in red)
        figsize: Figure size
        title: Plot title
    
    Returns:
        Matplotlib Figure
    """
    directed = is_directed_graph(matrix)
    G = create_networkx_graph(matrix, labels, directed)
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Compute layout if positions not provided
    if positions is None:
        positions = nx.spring_layout(G, seed=42, k=2)
    
    # Node colors
    node_colors = []
    n = len(matrix)
    for node in range(n):
        if node == current_node:
            node_colors.append('#FFD700')  # Gold for current
        elif node == source:
            node_colors.append('#4169E1')  # Royal Blue for source
        elif node == target:
            node_colors.append('#DC143C')  # Crimson for target
        elif visited and node in visited:
            node_colors.append('#32CD32')  # Lime Green for visited
        else:
            node_colors.append('#87CEEB')  # Sky Blue for unvisited
    
    # Edge colors and widths
    edge_colors = []
    edge_widths = []
    path_edges = set()
    
    if path and len(path) > 1:
        for i in range(len(path) - 1):
            path_edges.add((path[i], path[i + 1]))
            path_edges.add((path[i + 1], path[i]))  # For undirected
    
    for edge in G.edges():
        if edge in path_edges or (edge[1], edge[0]) in path_edges:
            edge_colors.append('#FF4500')  # Orange Red for path
            edge_widths.append(3.0)
        else:
            edge_colors.append('#708090')  # Slate Gray for normal
            edge_widths.append(1.5)
    
    # Draw the graph
    nx.draw_networkx_nodes(
        G, positions, 
        node_color=node_colors,
        node_size=700,
        ax=ax
    )
    
    # Draw node labels
    node_labels = {i: labels[i] if labels and i < len(labels) else str(i) for i in range(n)}
    nx.draw_networkx_labels(
        G, positions,
        labels=node_labels,
        font_size=12,
        font_weight='bold',
        ax=ax
    )
    
    # Draw edges
    if directed:
        nx.draw_networkx_edges(
            G, positions,
            edge_color=edge_colors,
            width=edge_widths,
            arrows=True,
            arrowsize=20,
            connectionstyle="arc3,rad=0.1",
            ax=ax
        )
    else:
        nx.draw_networkx_edges(
            G, positions,
            edge_color=edge_colors,
            width=edge_widths,
            ax=ax
        )
    
    # Draw edge weights
    edge_labels = nx.get_edge_attributes(G, 'weight')
    nx.draw_networkx_edge_labels(
        G, positions,
        edge_labels=edge_labels,
        font_size=10,
        ax=ax
    )
    
    # Add legend
    legend_elements = [
        mpatches.Patch(color='#4169E1', label='Source'),
        mpatches.Patch(color='#DC143C', label='Target'),
        mpatches.Patch(color='#FFD700', label='Current'),
        mpatches.Patch(color='#32CD32', label='Visited'),
        mpatches.Patch(color='#87CEEB', label='Unvisited'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', framealpha=0.9)
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()
    
    return fig


def visualize_graph_plotly(
    matrix: List[List[float]],
    labels: Optional[List[str]] = None,
    positions: Optional[Dict[int, Tuple[float, float]]] = None,
    visited: Optional[Set[int]] = None,
    current_node: Optional[int] = None,
    path: Optional[List[int]] = None,
    source: Optional[int] = None,
    target: Optional[int] = None,
    title: str = "Graph Visualization"
) -> go.Figure:
    """
    Create an interactive graph visualization using Plotly
    
    Returns:
        Plotly Figure
    """
    directed = is_directed_graph(matrix)
    G = create_networkx_graph(matrix, labels, directed)
    n = len(matrix)
    
    # Compute layout if positions not provided
    if positions is None:
        positions = nx.spring_layout(G, seed=42, k=2)
    
    # Normalize positions to dict if needed
    pos_dict = dict(positions)
    
    # Path edges for highlighting
    path_edges = set()
    if path and len(path) > 1:
        for i in range(len(path) - 1):
            path_edges.add((path[i], path[i + 1]))
            path_edges.add((path[i + 1], path[i]))
    
    # Create edge traces
    edge_traces = []
    annotations = []
    
    for edge in G.edges(data=True):
        x0, y0 = pos_dict[edge[0]]
        x1, y1 = pos_dict[edge[1]]
        weight = edge[2].get('weight', 1)
        
        is_path_edge = (edge[0], edge[1]) in path_edges or (edge[1], edge[0]) in path_edges
        
        edge_trace = go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode='lines',
            line=dict(
                width=4 if is_path_edge else 2,
                color='#FF4500' if is_path_edge else '#708090'
            ),
            hoverinfo='none'
        )
        edge_traces.append(edge_trace)
        
        # Edge weight annotation
        mid_x = (x0 + x1) / 2
        mid_y = (y0 + y1) / 2
        annotations.append(dict(
            x=mid_x,
            y=mid_y,
            text=str(weight),
            showarrow=False,
            font=dict(size=12, color='black'),
            bgcolor='white',
            borderpad=2
        ))
    
    # Create node trace
    node_x = []
    node_y = []
    node_colors = []
    node_text = []
    
    for node in range(n):
        x, y = pos_dict[node]
        node_x.append(x)
        node_y.append(y)
        
        label = labels[node] if labels and node < len(labels) else str(node)
        node_text.append(label)
        
        if node == current_node:
            node_colors.append('#FFD700')
        elif node == source:
            node_colors.append('#4169E1')
        elif node == target:
            node_colors.append('#DC143C')
        elif visited and node in visited:
            node_colors.append('#32CD32')
        else:
            node_colors.append('#87CEEB')
    
    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode='markers+text',
        marker=dict(
            size=40,
            color=node_colors,
            line=dict(width=2, color='#333333')
        ),
        text=node_text,
        textposition='middle center',
        textfont=dict(size=14, color='black', family='Arial Black'),
        hoverinfo='text',
        hovertext=[f"Node: {labels[i] if labels and i < len(labels) else i}" for i in range(n)]
    )
    
    # Combine all traces
    fig = go.Figure(data=edge_traces + [node_trace])
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        showlegend=False,
        hovermode='closest',
        annotations=annotations,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='white',
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return fig


def create_distance_table(
    distances: Dict[int, float],
    labels: Optional[List[str]] = None,
    source: int = 0
) -> List[Dict[str, Any]]:
    """
    Create a table of distances from source to all nodes
    
    Returns:
        List of dictionaries for table display
    """
    table_data = []
    
    for node, dist in sorted(distances.items()):
        label = labels[node] if labels and node < len(labels) else str(node)
        dist_str = "∞" if dist == float('inf') else f"{dist:.1f}"
        is_source = node == source
        
        table_data.append({
            "Node": label,
            "Distance": dist_str,
            "Status": "Source" if is_source else ("Unreachable" if dist == float('inf') else "Reachable")
        })
    
    return table_data
