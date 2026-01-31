"""
Dijkstra's Shortest Path Algorithm Implementation
With step-by-step execution history for visualization
"""

import heapq
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class AlgorithmStep:
    """Represents a single step in the algorithm execution"""
    step_number: int
    current_node: int
    visited: set
    distances: Dict[int, float]
    previous: Dict[int, Optional[int]]
    priority_queue: List[Tuple[float, int]]
    description: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'step_number': self.step_number,
            'current_node': self.current_node,
            'visited': list(self.visited),
            'distances': self.distances.copy(),
            'previous': self.previous.copy(),
            'priority_queue': list(self.priority_queue),
            'description': self.description
        }


@dataclass
class DijkstraResult:
    """Result of Dijkstra's algorithm execution"""
    distances: Dict[int, float]
    previous: Dict[int, Optional[int]]
    steps: List[AlgorithmStep]
    source: int
    
    def get_path(self, target: int) -> Optional[List[int]]:
        """Reconstruct the shortest path to target node"""
        if target not in self.distances or self.distances[target] == float('inf'):
            return None
        
        path = []
        current = target
        while current is not None:
            path.append(current)
            current = self.previous.get(current)
        
        path.reverse()
        return path
    
    def get_distance(self, target: int) -> float:
        """Get the shortest distance to target node"""
        return self.distances.get(target, float('inf'))


def matrix_to_adjacency_list(matrix: List[List[float]]) -> Dict[int, List[Tuple[int, float]]]:
    """
    Convert adjacency matrix to adjacency list
    
    Args:
        matrix: NxN adjacency matrix where matrix[i][j] is the weight of edge i->j
                Use 0 or float('inf') for no edge
    
    Returns:
        Dictionary mapping node index to list of (neighbor, weight) tuples
    """
    n = len(matrix)
    adj_list = {i: [] for i in range(n)}
    
    for i in range(n):
        for j in range(n):
            if i != j and matrix[i][j] > 0 and matrix[i][j] != float('inf'):
                adj_list[i].append((j, matrix[i][j]))
    
    return adj_list


def dijkstra(
    adj_matrix: List[List[float]], 
    source: int,
    node_labels: Optional[List[str]] = None
) -> DijkstraResult:
    """
    Execute Dijkstra's algorithm with step-by-step history
    
    Args:
        adj_matrix: NxN adjacency matrix
        source: Source node index
        node_labels: Optional list of node labels for descriptions
    
    Returns:
        DijkstraResult containing distances, paths, and execution steps
    """
    n = len(adj_matrix)
    
    if source < 0 or source >= n:
        raise ValueError(f"Source node {source} is out of range [0, {n-1}]")
    
    # Convert to adjacency list for efficient neighbor lookup
    adj_list = matrix_to_adjacency_list(adj_matrix)
    
    # Initialize
    distances = {i: float('inf') for i in range(n)}
    previous = {i: None for i in range(n)}
    visited = set()
    
    distances[source] = 0
    priority_queue = [(0, source)]
    
    steps = []
    step_number = 0
    
    # Node label helper
    def get_label(node: int) -> str:
        if node_labels and node < len(node_labels):
            return node_labels[node]
        return str(node)
    
    # Record initial state
    steps.append(AlgorithmStep(
        step_number=step_number,
        current_node=source,
        visited=visited.copy(),
        distances=distances.copy(),
        previous=previous.copy(),
        priority_queue=list(priority_queue),
        description=f"Initialize: Set distance to source node {get_label(source)} = 0, all others = infinity"
    ))
    
    while priority_queue:
        step_number += 1
        
        # Get node with minimum distance
        current_dist, current_node = heapq.heappop(priority_queue)
        
        # Skip if already visited
        if current_node in visited:
            continue
        
        # Mark as visited
        visited.add(current_node)
        
        # Record visiting step
        steps.append(AlgorithmStep(
            step_number=step_number,
            current_node=current_node,
            visited=visited.copy(),
            distances=distances.copy(),
            previous=previous.copy(),
            priority_queue=list(priority_queue),
            description=f"Visit node {get_label(current_node)} (distance = {current_dist})"
        ))
        
        # Explore neighbors
        for neighbor, weight in adj_list[current_node]:
            if neighbor in visited:
                continue
            
            new_dist = distances[current_node] + weight
            
            if new_dist < distances[neighbor]:
                old_dist = distances[neighbor]
                distances[neighbor] = new_dist
                previous[neighbor] = current_node
                heapq.heappush(priority_queue, (new_dist, neighbor))
                
                step_number += 1
                old_dist_str = "infinity" if old_dist == float('inf') else str(old_dist)
                steps.append(AlgorithmStep(
                    step_number=step_number,
                    current_node=current_node,
                    visited=visited.copy(),
                    distances=distances.copy(),
                    previous=previous.copy(),
                    priority_queue=list(priority_queue),
                    description=f"Update distance to {get_label(neighbor)}: {old_dist_str} -> {new_dist} (via {get_label(current_node)})"
                ))
    
    # Final step
    step_number += 1
    steps.append(AlgorithmStep(
        step_number=step_number,
        current_node=-1,
        visited=visited.copy(),
        distances=distances.copy(),
        previous=previous.copy(),
        priority_queue=[],
        description="Algorithm complete! All reachable nodes have been visited."
    ))
    
    return DijkstraResult(
        distances=distances,
        previous=previous,
        steps=steps,
        source=source
    )


def validate_matrix(matrix: List[List[float]]) -> Tuple[bool, str]:
    """
    Validate an adjacency matrix
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not matrix:
        return False, "Matrix is empty"
    
    n = len(matrix)
    
    for i, row in enumerate(matrix):
        if len(row) != n:
            return False, f"Row {i} has {len(row)} elements, expected {n}"
        
        for j, val in enumerate(row):
            if not isinstance(val, (int, float)):
                return False, f"Invalid value at [{i}][{j}]: {val}"
            if val < 0:
                return False, f"Negative weight at [{i}][{j}]: {val} (Dijkstra requires non-negative weights)"
    
    return True, "Valid"


def parse_matrix_string(matrix_str: str) -> Tuple[Optional[List[List[float]]], str]:
    """
    Parse a string representation of a matrix
    
    Formats supported:
    - Comma-separated rows, newline-separated: "1,2,3\\n4,5,6\\n7,8,9"
    - Space-separated: "1 2 3\\n4 5 6\\n7 8 9"
    
    Returns:
        Tuple of (matrix or None, error_message)
    """
    try:
        lines = [line.strip() for line in matrix_str.strip().split('\n') if line.strip()]
        
        if not lines:
            return None, "No data provided"
        
        matrix = []
        for i, line in enumerate(lines):
            # Try comma-separated first, then space-separated
            if ',' in line:
                values = [v.strip() for v in line.split(',') if v.strip()]
            else:
                values = line.split()
            
            row = []
            for j, v in enumerate(values):
                try:
                    if v.lower() in ('inf', 'infinity', '∞'):
                        row.append(float('inf'))
                    else:
                        row.append(float(v))
                except ValueError:
                    return None, f"Invalid number at row {i+1}, column {j+1}: '{v}'"
            
            matrix.append(row)
        
        # Validate square matrix
        n = len(matrix)
        for i, row in enumerate(matrix):
            if len(row) != n:
                return None, f"Matrix is not square: row {i+1} has {len(row)} elements, expected {n}"
        
        # Validate the matrix
        is_valid, msg = validate_matrix(matrix)
        if not is_valid:
            return None, msg
        
        return matrix, "Success"
    
    except Exception as e:
        return None, f"Parse error: {str(e)}"
