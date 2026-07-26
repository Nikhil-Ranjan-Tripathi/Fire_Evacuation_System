import json
import time
import heapq
import math
from typing import Dict, List, Tuple, Optional, Any, Set
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RoutingEngine:
    FIRE_LEVELS = {
        'none': 0,
        'low': 1,
        'medium': 2,
        'high': 3,
        'flashover': 4
    }
    FIRE_PENALTIES = {
        'none': 1.0,
        'low': 8.0,
        'medium': 20.0,
        'high': 60.0,
        'flashover': float('inf')
    }
    RISK_MULTIPLIERS = {
        'none': 0.0,
        'low': 0.5,
        'medium': 2.0,
        'high': 6.0
    }
    STAGES = [
        {'name': 'Stage 1 - Safe Only', 'allowed': {'none'}},
        {'name': 'Stage 2 - Moderate Risk', 'allowed': {'none', 'low', 'medium'}},
        {'name': 'Stage 3 - High Risk', 'allowed': {'none', 'low', 'medium', 'high'}},
    ]
    
    def __init__(self, building_config_path: str = "data/building_grid.json"):
        with open(building_config_path, 'r') as f:
            self.building_data = json.load(f)
        self.nodes = self.building_data['nodes']
        self.exits = set(self.building_data['exits'])
        self.thresholds = self.building_data.get('thresholds', {})
        self.node_positions = {
            node['id']: (node.get('x', 0), node.get('y', 0))
            for node in self.nodes
        }
        self.graph = self._build_graph()
        self.node_weights = {
            node['id']: 1.0
            for node in self.nodes
        }
        self.latest_sensor_data = {}
        self.route_cache = {}
        self.last_compute_time = 0
        
        logger.info("✅ Routing Engine initialized with %d nodes, %d exits",
                   len(self.nodes), len(self.exits))
        logger.info("📍 Staged routing with %d stages", len(self.STAGES))
        logger.info("🔥 Fire levels: %s", list(self.FIRE_LEVELS.keys()))
    
    def _build_graph(self) -> Dict[str, Dict[str, float]]:
        graph = defaultdict(dict)
        
        for node in self.nodes:
            node_id = node['id']
            for connection in node.get('connections', []):
                distance = self._distance(node_id, connection)
                graph[node_id][connection] = distance
                graph[connection][node_id] = distance
        
        return graph
    
    def _distance(self, node1: str, node2: str) -> float:
        x1, y1 = self.node_positions.get(node1, (0, 0))
        x2, y2 = self.node_positions.get(node2, (0, 0))
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    
    def _heuristic(self, node: str, goal: str) -> float:
        return self._distance(node, goal)
    
    def _get_fire_level(self, node_id: str) -> str:
        sensor = self.latest_sensor_data.get(node_id, {})
        return sensor.get('fire_level', 'none')
    
    def _movement_cost(self, current: str, neighbor: str, allowed_levels: Set[str]) -> float:
        fire_level = self._get_fire_level(neighbor)
        if fire_level not in allowed_levels:
            return float('inf')
        distance = self.graph[current][neighbor]
        risk = self.RISK_MULTIPLIERS.get(fire_level, 0.0)
        return distance * (1 + risk)
    
    def _astar(self, start: str, goal: str, allowed_levels: Set[str]) -> Tuple[Optional[List[str]], float]:

        cache_key = (start, goal, tuple(sorted(allowed_levels)))
        if cache_key in self.route_cache:
            cached_time, path, cost = self.route_cache[cache_key]
            if time.time() - cached_time < 1.0:
                return path.copy(), cost
        
        open_set = []
        heapq.heappush(open_set, (0, start))
        
        came_from = {}
        
        g_score = {node: float('inf') for node in self.graph}
        g_score[start] = 0
        
        f_score = {node: float('inf') for node in self.graph}
        f_score[start] = self._heuristic(start, goal)
        
        closed_set = set()
        
        while open_set:
            _, current = heapq.heappop(open_set)
            
            if current in closed_set:
                continue
            
            closed_set.add(current)
            
            if current == goal:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                
                cost = g_score[goal]
                self.route_cache[cache_key] = (time.time(), path.copy(), cost)
                
                return path, cost
            
            for neighbor in self.graph.get(current, {}):
                if neighbor in closed_set:
                    continue
                
                move_cost = self._movement_cost(current, neighbor, allowed_levels)
                if move_cost == float('inf'):
                    continue
                
                tentative_g = g_score[current] + move_cost
                
                if tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        return None, float('inf')
    
    def find_safest_route(self, start_node: str) -> Tuple[List[str], float]:
        if start_node not in self.graph:
            logger.warning("Start node %s not in graph", start_node)
            return [start_node], float('inf')

        cache_key = ('route', start_node)
        if cache_key in self.route_cache:
            cached_time, path, cost = self.route_cache[cache_key]
            if time.time() - cached_time < 2.0:
                return path.copy(), cost
        
        start_time = time.time()
        best_path = None
        best_cost = float('inf')
        stage_used = None

        for stage in self.STAGES:
            allowed_levels = stage['allowed']
            stage_name = stage['name']
            for exit_node in self.exits:
                if start_node == exit_node:
                    return [start_node], 0.0
                
                path, cost = self._astar(start_node, exit_node, allowed_levels)
                
                if path is not None and cost < best_cost:
                    best_cost = cost
                    best_path = path
                    stage_used = stage_name

            if best_path is not None:
                break
        
        compute_time = (time.time() - start_time) * 1000
        self.last_compute_time = compute_time
        
        if best_path is None:
            logger.warning("❌ No route found from %s to any exit", start_node)
            fallback_path, fallback_cost = self._find_fallback_route(start_node)
            self.route_cache[cache_key] = (time.time(), fallback_path.copy(), fallback_cost)
            return fallback_path, fallback_cost

        if stage_used:
            logger.debug("Route found using %s (cost: %.2f)", stage_used, best_cost)
        
        self.route_cache[cache_key] = (time.time(), best_path.copy(), best_cost)
        return best_path, best_cost
    
    def _find_fallback_route(self, start_node: str) -> Tuple[List[str], float]:
        allowed = {'none', 'low', 'medium', 'high'}
        best_path = None
        best_cost = float('inf')
        
        for exit_node in self.exits:
            path, cost = self._astar(start_node, exit_node, allowed)
            if path is not None and cost < best_cost:
                best_cost = cost
                best_path = path

        if best_path is None:
            logger.error("❌ Even fallback routing failed from %s", start_node)
            return [start_node], float('inf')
        
        return best_path, best_cost
    
    def update_weights(self, sensor_data: Dict[str, Dict]):
        self.latest_sensor_data = sensor_data
        start_time = time.time()
        self.route_cache.clear()
        for node_id, data in sensor_data.items():
            if node_id not in self.node_weights:
                continue
            self.node_weights[node_id] = self._calculate_node_weight(node_id, data)
        self.last_compute_time = (time.time() - start_time) * 1000
    
    def _calculate_node_weight(self, node_id: str, sensor_data: Dict) -> float:
        fire_level = sensor_data.get('fire_level', 'none')
        penalty = self.FIRE_PENALTIES.get(fire_level, 1.0)
        
        if penalty == float('inf'):
            return float('inf')
        
        return penalty
    
    def _is_blocked(self, node_id: str, sensor_data: Dict) -> bool:
        fire_level = sensor_data.get('fire_level', 'none')
        if fire_level == 'flashover':
            return True
        
        return False
    
    def get_route_info(self, start_node: str) -> Dict[str, Any]:
        path, cost = self.find_safest_route(start_node)
        safe_count = 0
        hazard_count = 0
        hazard_nodes = []
        for node in path:
            level = self._get_fire_level(node)
            if level == 'none':
                safe_count += 1
            else:
                hazard_count += 1
                hazard_nodes.append(node)
        fire_levels = []
        for node in path:
            level = self._get_fire_level(node)
            fire_levels.append(level)
        
        return {
            'start_node': start_node,
            'path': path,
            'total_cost': cost,
            'path_length': len(path),
            'safe_nodes': safe_count,
            'hazard_nodes': hazard_nodes,
            'hazard_count': hazard_count,
            'fire_levels': fire_levels,
            'computation_time_ms': self.last_compute_time,
            'is_safe': hazard_count == 0,
            'timestamp': time.time()
        }
    
    def get_node_fire_level(self, node_id: str) -> str:
        return self._get_fire_level(node_id)
    
    def clear_cache(self):
        self.route_cache.clear()
        logger.debug("Route cache cleared")

if __name__ == "__main__":
    print("🧪 Testing Routing Engine...")

    engine = RoutingEngine()
    mock_sensors = {
        'N-01': {'fire_level': 'none'},
        'N-02': {'fire_level': 'none'},
        'N-03': {'fire_level': 'none'},
        'N-05': {'fire_level': 'high'},
        'N-09': {'fire_level': 'flashover'},
        'N-15': {'fire_level': 'low'},
    }
    engine.update_weights(mock_sensors)
    path, cost = engine.find_safest_route('N-01')
    print(f"\n📍 Route from N-01: {' → '.join(path)}")
    print(f"📊 Cost: {cost:.2f}")
    info = engine.get_route_info('N-01')
    print(f"\n📋 Route Info:")
    print(f"   Length: {info['path_length']} nodes")
    print(f"   Safe nodes: {info['safe_nodes']}")
    print(f"   Hazard nodes: {info['hazard_nodes']}")
    print(f"   Fire levels: {info['fire_levels']}")