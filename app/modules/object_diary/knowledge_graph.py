"""Knowledge Graph - Graph of relationships between construction objects.

This module builds and maintains a knowledge graph of relationships
between construction objects using SQLite and edge tracking.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

from app.modules.storage.database import get_db_connection

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """
    Knowledge graph for construction object relationships.
    
    Maintains a graph of object relationships stored in SQLite
    with support for different edge types (parent-child, related, references).
    """
    
    def __init__(self):
        """Initialize Knowledge Graph."""
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create necessary database tables."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Object edges table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS object_edges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_object_id TEXT NOT NULL,
                        target_object_id TEXT NOT NULL,
                        edge_type TEXT NOT NULL,
                        weight REAL DEFAULT 1.0,
                        metadata TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for fast lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_edges_source
                    ON object_edges(source_object_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_edges_target
                    ON object_edges(target_object_id)
                """)
                
                logger.info("Knowledge Graph tables initialized")
                
        except Exception as e:
            logger.error(f"Error creating Knowledge Graph tables: {e}")
    
    def add_edge(
        self,
        source_object_id: str,
        target_object_id: str,
        edge_type: str,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Add an edge between objects.
        
        Args:
            source_object_id: Source object ID
            target_object_id: Target object ID
            edge_type: Type of relationship (parent, related, reference, etc.)
            weight: Edge weight (confidence/strength)
            metadata: Additional metadata
            
        Returns:
            Edge ID
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO object_edges (
                        source_object_id, target_object_id, edge_type, weight, metadata
                    ) VALUES (?, ?, ?, ?, ?)
                """, (source_object_id, target_object_id, edge_type, weight, str(metadata or {})))
                
                edge_id = cursor.lastrowid
                logger.info(f"Added edge: {source_object_id} -> {target_object_id} ({edge_type})")
                return edge_id
                
        except Exception as e:
            logger.error(f"Error adding edge: {e}")
            return -1
    
    def get_neighbors(
        self,
        object_id: str,
        edge_type: Optional[str] = None,
        direction: str = "outgoing"
    ) -> List[Dict[str, Any]]:
        """
        Get neighboring objects.
        
        Args:
            object_id: Object ID
            edge_type: Filter by edge type (optional)
            direction: "outgoing", "incoming", or "both"
            
        Returns:
            List of neighboring objects
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                neighbors = []
                
                if direction in ["outgoing", "both"]:
                    if edge_type:
                        cursor.execute("""
                            SELECT * FROM object_edges
                            WHERE source_object_id = ? AND edge_type = ?
                        """, (object_id, edge_type))
                    else:
                        cursor.execute("""
                            SELECT * FROM object_edges
                            WHERE source_object_id = ?
                        """, (object_id,))
                    
                    for row in cursor.fetchall():
                        neighbors.append({
                            'id': row['id'],
                            'target': row['target_object_id'],
                            'edge_type': row['edge_type'],
                            'weight': row['weight'],
                            'direction': 'outgoing'
                        })
                
                if direction in ["incoming", "both"]:
                    if edge_type:
                        cursor.execute("""
                            SELECT * FROM object_edges
                            WHERE target_object_id = ? AND edge_type = ?
                        """, (object_id, edge_type))
                    else:
                        cursor.execute("""
                            SELECT * FROM object_edges
                            WHERE target_object_id = ?
                        """, (object_id,))
                    
                    for row in cursor.fetchall():
                        neighbors.append({
                            'id': row['id'],
                            'source': row['source_object_id'],
                            'edge_type': row['edge_type'],
                            'weight': row['weight'],
                            'direction': 'incoming'
                        })
                
                return neighbors
                
        except Exception as e:
            logger.error(f"Error getting neighbors: {e}")
            return []
    
    def find_shortest_path(
        self,
        source_object_id: str,
        target_object_id: str
    ) -> List[str]:
        """
        Find shortest path between two objects (BFS).
        
        Args:
            source_object_id: Source object ID
            target_object_id: Target object ID
            
        Returns:
            List of object IDs in path
        """
        try:
            # BFS to find shortest path
            visited = set()
            queue = [(source_object_id, [])]
            
            while queue:
                current, path = queue.pop(0)
                
                if current == target_object_id:
                    return path + [current]
                
                if current in visited:
                    continue
                
                visited.add(current)
                
                # Get neighbors
                neighbors = self.get_neighbors(current, direction="outgoing")
                for neighbor in neighbors:
                    if neighbor['target'] not in visited:
                        queue.append((neighbor['target'], path + [current]))
            
            return []  # No path found
            
        except Exception as e:
            logger.error(f"Error finding shortest path: {e}")
            return []
    
    def get_connected_components(self) -> List[Set[str]]:
        """
        Find all connected components in the graph.
        
        Returns:
            List of connected components (sets of object IDs)
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT source_object_id FROM object_edges")
                
                all_objects = {row['source_object_id'] for row in cursor.fetchall()}
                
                visited = set()
                components = []
                
                for obj in all_objects:
                    if obj not in visited:
                        # BFS to find component
                        component = set()
                        queue = [obj]
                        
                        while queue:
                            current = queue.pop(0)
                            if current in visited:
                                continue
                            
                            visited.add(current)
                            component.add(current)
                            
                            neighbors = self.get_neighbors(current, direction="both")
                            for neighbor in neighbors:
                                target = neighbor['target'] if neighbor['direction'] == 'outgoing' else neighbor['source']
                                if target not in visited:
                                    queue.append(target)
                        
                        components.append(component)
                
                return components
                
        except Exception as e:
            logger.error(f"Error finding connected components: {e}")
            return []


if __name__ == "__main__":
    # Test Knowledge Graph
    logging.basicConfig(level=logging.INFO)
    
    graph = KnowledgeGraph()
    
    # Add test edges
    graph.add_edge("OBJ-001", "OBJ-002", "parent")
    graph.add_edge("OBJ-002", "OBJ-003", "related")
    
    # Get neighbors
    neighbors = graph.get_neighbors("OBJ-001")
    print(f"Neighbors of OBJ-001: {neighbors}")
    
    # Find path
    path = graph.find_shortest_path("OBJ-001", "OBJ-003")
    print(f"Shortest path: {path}")
    
    # Get connected components
    components = graph.get_connected_components()
    print(f"Connected components: {len(components)}")
