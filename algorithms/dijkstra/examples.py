"""
Predefined example graphs for Dijkstra's algorithm visualization
"""

from typing import List, Dict, Tuple, Any


def get_example_graphs() -> Dict[str, Dict[str, Any]]:
    """
    Returns a dictionary of predefined example graphs
    
    Each graph contains:
    - matrix: adjacency matrix
    - labels: node labels
    - description: description of the graph
    - positions: optional node positions for visualization
    - default_source: suggested source node
    - default_target: suggested target node
    """
    
    examples = {
        "Simple 5-Node Graph": {
            "matrix": [
                [0, 4, 2, 0, 0],
                [4, 0, 1, 5, 0],
                [2, 1, 0, 8, 10],
                [0, 5, 8, 0, 2],
                [0, 0, 10, 2, 0]
            ],
            "labels": ["A", "B", "C", "D", "E"],
            "description": "A simple undirected weighted graph with 5 nodes. Good for learning the basics.",
            "positions": {
                0: (0, 1),
                1: (1, 2),
                2: (1, 0),
                3: (2, 1),
                4: (3, 1)
            },
            "default_source": 0,
            "default_target": 4
        },
        
        "City Road Network": {
            "matrix": [
                [0, 10, 0, 0, 15, 5],
                [10, 0, 10, 30, 0, 0],
                [0, 10, 0, 12, 5, 0],
                [0, 30, 12, 0, 0, 20],
                [15, 0, 5, 0, 0, 0],
                [5, 0, 0, 20, 0, 0]
            ],
            "labels": ["Home", "Mall", "Park", "Office", "School", "Gym"],
            "description": "A city road network with distances in minutes. Find the fastest route!",
            "positions": {
                0: (0, 1),
                1: (1, 2),
                2: (2, 2),
                3: (3, 1),
                4: (1, 0),
                5: (0, 0)
            },
            "default_source": 0,
            "default_target": 3
        },
        
        "Weighted Grid (4x4)": {
            "matrix": [
                [0, 1, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [1, 0, 3, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 3, 0, 2, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                [0, 0, 2, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
                [2, 0, 0, 0, 0, 2, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 2, 0, 1, 0, 0, 2, 0, 0, 0, 0, 0, 0],
                [0, 0, 4, 0, 0, 1, 0, 3, 0, 0, 1, 0, 0, 0, 0, 0],
                [0, 0, 0, 1, 0, 0, 3, 0, 0, 0, 0, 2, 0, 0, 0, 0],
                [0, 0, 0, 0, 3, 0, 0, 0, 0, 1, 0, 0, 4, 0, 0, 0],
                [0, 0, 0, 0, 0, 2, 0, 0, 1, 0, 2, 0, 0, 3, 0, 0],
                [0, 0, 0, 0, 0, 0, 1, 0, 0, 2, 0, 1, 0, 0, 2, 0],
                [0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 1, 0, 0, 0, 0, 3],
                [0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 2, 0, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 2, 0, 1, 0],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 1, 0, 2],
                [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 2, 0]
            ],
            "labels": [f"{i}" for i in range(16)],
            "description": "A 4x4 grid graph where each node connects to its neighbors. Navigate from corner to corner!",
            "positions": {
                i: (i % 4, 3 - i // 4) for i in range(16)
            },
            "default_source": 0,
            "default_target": 15
        },
        
        "Directed Graph": {
            "matrix": [
                [0, 5, 10, 0, 0, 0],
                [0, 0, 3, 9, 2, 0],
                [0, 0, 0, 0, 1, 0],
                [0, 0, 0, 0, 0, 4],
                [0, 0, 0, 6, 0, 2],
                [7, 0, 0, 0, 0, 0]
            ],
            "labels": ["S", "A", "B", "C", "D", "T"],
            "description": "A directed weighted graph. Note that edges only go one way!",
            "positions": {
                0: (0, 1),
                1: (1, 2),
                2: (1, 0),
                3: (2, 2),
                4: (2, 0),
                5: (3, 1)
            },
            "default_source": 0,
            "default_target": 5
        },
        
        "Sparse Network": {
            "matrix": [
                [0, 7, 0, 0, 0, 14, 9, 0],
                [7, 0, 10, 15, 0, 0, 0, 0],
                [0, 10, 0, 11, 0, 0, 0, 2],
                [0, 15, 11, 0, 6, 0, 0, 0],
                [0, 0, 0, 6, 0, 9, 0, 0],
                [14, 0, 0, 0, 9, 0, 2, 0],
                [9, 0, 0, 0, 0, 2, 0, 0],
                [0, 0, 2, 0, 0, 0, 0, 0]
            ],
            "labels": ["1", "2", "3", "4", "5", "6", "7", "8"],
            "description": "A sparse graph with 8 nodes but few connections. Some paths require many hops!",
            "positions": {
                0: (0, 2),
                1: (1, 3),
                2: (2, 3),
                3: (2, 2),
                4: (2, 1),
                5: (1, 0),
                6: (0, 1),
                7: (3, 3)
            },
            "default_source": 0,
            "default_target": 7
        },
        
        "Dense Complete Graph": {
            "matrix": [
                [0, 3, 7, 5, 2],
                [3, 0, 4, 6, 8],
                [7, 4, 0, 2, 5],
                [5, 6, 2, 0, 3],
                [2, 8, 5, 3, 0]
            ],
            "labels": ["P", "Q", "R", "S", "T"],
            "description": "A complete graph where every node connects to every other node. Many possible paths!",
            "positions": {
                0: (1, 2),
                1: (0, 1),
                2: (0.5, 0),
                3: (1.5, 0),
                4: (2, 1)
            },
            "default_source": 0,
            "default_target": 3
        },
        
        "Tree Structure": {
            "matrix": [
                [0, 4, 3, 0, 0, 0, 0],
                [4, 0, 0, 5, 2, 0, 0],
                [3, 0, 0, 0, 0, 6, 4],
                [0, 5, 0, 0, 0, 0, 0],
                [0, 2, 0, 0, 0, 0, 0],
                [0, 0, 6, 0, 0, 0, 0],
                [0, 0, 4, 0, 0, 0, 0]
            ],
            "labels": ["Root", "L1", "R1", "L2", "L3", "R2", "R3"],
            "description": "A tree structure - there's only one path between any two nodes!",
            "positions": {
                0: (1.5, 3),
                1: (0.5, 2),
                2: (2.5, 2),
                3: (0, 1),
                4: (1, 1),
                5: (2, 1),
                6: (3, 1)
            },
            "default_source": 3,
            "default_target": 6
        }
    }
    
    return examples


def get_example_names() -> List[str]:
    """Get list of available example names"""
    return list(get_example_graphs().keys())


def get_example(name: str) -> Dict[str, Any]:
    """Get a specific example by name"""
    examples = get_example_graphs()
    if name not in examples:
        raise ValueError(f"Example '{name}' not found. Available: {list(examples.keys())}")
    return examples[name]
