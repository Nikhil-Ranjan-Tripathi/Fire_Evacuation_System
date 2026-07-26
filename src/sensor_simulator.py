import json
import random
import time
import threading
import copy
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SensorSimulator:

    def __init__(self, config_path: str = "data/sensor_config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.active = False
        self.sensor_data = {}
        self.manual_overrides = {}
        self.lock = threading.RLock()
        self.thread = None
        
        with open("data/building_grid.json", 'r') as f:
            building_data = json.load(f)
            self.nodes = building_data['nodes']
        
        self._initialize_sensors()
        logger.info("Sensor Simulator initialized with %d nodes", len(self.nodes))
    
    def _initialize_sensors(self):
        with self.lock:
            for node in self.nodes:
                node_id = node['id']
                self.sensor_data[node_id] = {
                    'node_id': node_id,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'temperature': random.uniform(20.0, 25.0),
                    'smoke_density': random.uniform(0, 20),
                    'flame_presence': False,
                    'battery_status': random.uniform(85, 100),
                    'status': 'normal'
                }
    
    def start(self):
        if self.active:
            return
        
        self.active = True
        self.thread = threading.Thread(target=self._run_simulation, daemon=True)
        self.thread.start()
        logger.info("Sensor simulator started")
    
    def stop(self):
        self.active = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Sensor simulator stopped")
    
    def _run_simulation(self):
        while self.active:
            try:
                self._update_sensors()
                time.sleep(self.config.get('update_interval', 0.5))
            except Exception as e:
                logger.error("Error in sensor simulation: %s", e)
    
    def _update_sensors(self):
        with self.lock:
            for node_id in self.sensor_data:
                if node_id in self.manual_overrides:
                    continue
                
                current = self.sensor_data[node_id]
                temp_change = random.uniform(-0.5, 0.5)
                smoke_change = random.uniform(-2, 2)
                
                if random.random() < 0.001:
                    self._trigger_fire_event(node_id)
                    continue
                
                current['temperature'] = max(15, min(800, current['temperature'] + temp_change))
                current['smoke_density'] = max(0, min(1000, current['smoke_density'] + smoke_change))
                current['timestamp'] = datetime.utcnow().isoformat() + 'Z'
                current['battery_status'] = max(0, min(100, current['battery_status'] + random.uniform(-0.5, 0.5)))
                current['status'] = self._calculate_status(current)
    
    def _trigger_fire_event(self, node_id: str):
        with self.lock:
            if node_id in self.sensor_data:
                self.sensor_data[node_id].update({
                    'temperature': random.uniform(200, 800),
                    'smoke_density': random.uniform(600, 1000),
                    'flame_presence': True,
                    'status': 'critical'
                })
                logger.warning("🔥 FIRE EVENT TRIGGERED at node %s", node_id)
    
    def _calculate_status(self, data: Dict) -> str:
        temp = data['temperature']
        smoke = data['smoke_density']
        flame = data['flame_presence']
        
        if flame or temp > 200 or smoke > 700:
            return 'critical'
        elif temp > 60 or smoke > 500:
            return 'warning'
        elif temp > 40 or smoke > 100:
            return 'caution'
        else:
            return 'normal'
    
    def get_sensor_data(self, node_id: Optional[str] = None) -> Dict:
        with self.lock:
            if node_id:
                data = self.sensor_data.get(node_id, {})
                return copy.deepcopy(data) if data else {}
            return copy.deepcopy(self.sensor_data)
    
    def manual_override(self, node_id: str, data: Dict):
        with self.lock:
            if node_id in self.sensor_data:
                self.sensor_data[node_id].update(data)
                self.sensor_data[node_id]['timestamp'] = datetime.utcnow().isoformat() + 'Z'
                self.sensor_data[node_id]['status'] = self._calculate_status(
                    self.sensor_data[node_id]
                )
                self.manual_overrides[node_id] = True
                logger.info("Manual override applied to node %s", node_id)
    
    def clear_override(self, node_id: str):
        with self.lock:
            if node_id in self.manual_overrides:
                del self.manual_overrides[node_id]
                logger.info("Manual override cleared for node %s", node_id)
    
    def inject_fire_scenario(self, node_ids: List[str], severity: str = 'medium'):
        severity_params = {
            'low': {'temp': 80, 'smoke': 300, 'flame': False},
            'medium': {'temp': 300, 'smoke': 600, 'flame': True},
            'high': {'temp': 450, 'smoke': 800, 'flame': True},
            'flashover': {'temp': 700, 'smoke': 950, 'flame': True}
        }
        
        params = severity_params.get(severity, severity_params['medium'])
        with self.lock:
            for node_id in node_ids:
                if node_id in self.sensor_data:
                    self.sensor_data[node_id].update({
                        'temperature': random.uniform(params['temp']*0.8, params['temp']*1.2),
                        'smoke_density': random.uniform(params['smoke']*0.8, params['smoke']*1.2),
                        'flame_presence': params['flame'],
                        'status': 'critical'
                    })
                    self.manual_overrides[node_id] = True
        
        logger.info("🔥 Fire scenario injected: %s on nodes %s", severity, node_ids)
    
    def get_data_packet(self, node_id: str) -> Dict:
        data = self.get_sensor_data(node_id)
        if not data:
            return {}
        
        return {
            'node_id': data['node_id'],
            'timestamp': data['timestamp'],
            'temperature': round(data['temperature'], 2),
            'smoke_density': round(data['smoke_density'], 2),
            'flame_presence': data['flame_presence'],
            'battery_status': round(data['battery_status'], 2),
            'status': data['status']
        }