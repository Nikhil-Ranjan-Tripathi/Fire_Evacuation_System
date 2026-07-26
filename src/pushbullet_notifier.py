import json
import logging
import requests
from typing import Dict, List, Optional, Any
import os
import time
import hashlib
from datetime import datetime

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class PushbulletNotifier:
    
    def __init__(self, config_path: str = "data/pushbullet_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.api_key = self.config.get('api_key', '')
        self.users = self.config.get('users', [])
        self.base_url = 'https://api.pushbullet.com/v2'
        self.headers = {'Access-Token': self.api_key, 'Content-Type': 'application/json'}
        self.is_configured = False
        self.is_offline = False
        self.offline_queue = []
        self.max_offline_queue = 50
        
        if self.api_key and self.api_key != "YOUR_PUSHBULLET_API_KEY_HERE":
            self.is_configured = self._test_connection()
            if self.is_configured:
                logger.info("Pushbullet connected")
            else:
                logger.warning("Pushbullet connection failed - running in offline mode")
                self.is_offline = True
        else:
            logger.warning("Pushbullet API key not configured")
        
        self.last_fire_levels = {}
        self.last_route = None
        self.last_exit = None
        
        self.last_sent = {}
        
        self.cooldowns = {
            "fire": 30,
            "route": 60,
            "exit": 0,
            "system": 120,
            "critical": 0,
            "escalation": 300
        }
        
        self.pending_events = []
        self.batch_window = 2
        self.batch_start_time = None
        self._last_alert_time = 0
        self._alert_cooldown = 30
        
        self._sent_event_ids = set()
        self._sent_event_timeout = 10
        
        self._retry_count = 0
        self._max_retries = 3
        self._retry_delay = 2
        
        self._initialized = True
    
    def _load_config(self) -> Dict:
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            default = {
                "api_key": "YOUR_PUSHBULLET_API_KEY_HERE",
                "users": [
                    {
                        "id": "your_email@example.com", 
                        "name": "Emergency Contact", 
                        "devices": []
                    }
                ]
            }
            with open(self.config_path, 'w') as f:
                json.dump(default, f, indent=2)
            logger.info(f"Created default config at {self.config_path}")
            return default
    
    def _test_connection(self) -> bool:
        try:
            response = requests.get(
                f"{self.base_url}/users/me", 
                headers=self.headers, 
                timeout=3
            )
            return response.status_code == 200
        except requests.exceptions.Timeout:
            logger.warning("Pushbullet connection timeout")
            return False
        except requests.exceptions.ConnectionError:
            logger.warning("Pushbullet connection error")
            return False
        except Exception as e:
            logger.error(f"Pushbullet connection error: {e}")
            return False
    
    def _severity_value(self, level: str) -> int:
        order = {
            "none": 0,
            "low": 1,
            "medium": 2,
            "high": 3,
            "flashover": 4
        }
        return order.get(level.lower(), 0)
    
    def _generate_event_id(self, event_type: str, identifier: str) -> str:
        raw = f"{event_type}_{identifier}_{time.time()}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]
    
    def _is_duplicate(self, event_id: str) -> bool:
        if event_id in self._sent_event_ids:
            return True
        self._sent_event_ids.add(event_id)
        if len(self._sent_event_ids) > 100:
            self._sent_event_ids.clear()
        return False
    
    def _can_send(self, key: str, cooldown: int) -> bool:
        now = time.time()
        last = self.last_sent.get(key, 0)
        if now - last >= cooldown:
            self.last_sent[key] = now
            return True
        return False
    
    def _can_send_alert(self) -> bool:
        now = time.time()
        if now - self._last_alert_time >= self._alert_cooldown:
            self._last_alert_time = now
            return True
        return False
    
    def _send_with_retry(self, title: str, body: str) -> bool:
        if self.is_offline:
            self._queue_offline(title, body)
            return False
        
        for attempt in range(self._max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/pushes",
                    headers=self.headers,
                    json={
                        'type': 'note',
                        'title': title[:100],
                        'body': body[:200],
                        'priority': 2
                    },
                    timeout=5
                )
                if response.status_code == 200:
                    self._retry_count = 0
                    self.is_offline = False
                    return True
                elif response.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    if attempt == self._max_retries - 1:
                        self._queue_offline(title, body)
                    continue
            except requests.exceptions.Timeout:
                if attempt == self._max_retries - 1:
                    self.is_offline = True
                    self._queue_offline(title, body)
                else:
                    time.sleep(self._retry_delay * (attempt + 1))
            except requests.exceptions.ConnectionError:
                if attempt == self._max_retries - 1:
                    self.is_offline = True
                    self._queue_offline(title, body)
                else:
                    time.sleep(self._retry_delay * (attempt + 1))
            except Exception as e:
                logger.error(f"Push error: {e}")
                if attempt == self._max_retries - 1:
                    self._queue_offline(title, body)
                else:
                    time.sleep(self._retry_delay * (attempt + 1))
        
        return False
    
    def _queue_offline(self, title: str, body: str):
        if len(self.offline_queue) < self.max_offline_queue:
            self.offline_queue.append({
                'title': title,
                'body': body,
                'timestamp': time.time()
            })
        else:
            self.offline_queue.pop(0)
            self.offline_queue.append({
                'title': title,
                'body': body,
                'timestamp': time.time()
            })
    
    def retry_offline_queue(self) -> int:
        if not self.offline_queue:
            return 0
        
        if not self.is_configured:
            return 0
        
        self.is_offline = False
        successful = 0
        
        for item in self.offline_queue[:]:
            if self._send_with_retry(item['title'], item['body']):
                self.offline_queue.remove(item)
                successful += 1
            else:
                break
        
        return successful
    
    def _queue_event(self, message: str, severity: int = 0):
        if self.batch_start_time is None:
            self.batch_start_time = time.time()
        
        self.pending_events.append({
            'message': message,
            'severity': severity,
            'timestamp': time.time()
        })
    
    def _flush_events(self) -> bool:
        if not self.pending_events:
            return False
        
        critical_events = [e for e in self.pending_events if e['severity'] >= 3]
        urgent_events = [e for e in self.pending_events if e['severity'] >= 2]
        
        if critical_events:
            title = "EVACUATION ALERT"
            body = ""
            for event in critical_events[:3]:
                body += f"• {event['message']}\n"
            if len(critical_events) > 3:
                body += f"• +{len(critical_events) - 3} more critical events\n"
        elif urgent_events:
            title = "Urgent - Fire Update"
            body = ""
            for event in urgent_events[:5]:
                body += f"• {event['message']}\n"
            if len(urgent_events) > 5:
                body += f"• +{len(urgent_events) - 5} more updates\n"
        else:
            title = "Fire Evacuation Update"
            body = ""
            for event in self.pending_events[:5]:
                body += f"• {event['message']}\n"
            if len(self.pending_events) > 5:
                body += f"• +{len(self.pending_events) - 5} more updates\n"
        
        body += f"\nTime: {time.strftime('%H:%M:%S')}"
        
        self.pending_events.clear()
        self.batch_start_time = None
        
        return self._send_with_retry(title, body)
    
    def update(self):
        if self.batch_start_time is None:
            return
        
        if time.time() - self.batch_start_time >= self.batch_window:
            self._flush_events()
    
    def process_fire_update(self, node_id: str, fire_level: str, sensor_data: Dict) -> bool:
        if not self.is_configured:
            return False
        
        previous_level = self.last_fire_levels.get(node_id, 'none')
        
        if previous_level == fire_level:
            return False
        
        self.last_fire_levels[node_id] = fire_level
        
        current_severity = self._severity_value(fire_level)
        previous_severity = self._severity_value(previous_level)
        
        event_id = self._generate_event_id('fire', f"{node_id}_{fire_level}")
        if self._is_duplicate(event_id):
            return False
        
        if fire_level == 'none' and previous_level != 'none':
            if self._can_send(f"fire_{node_id}", 30):
                self._queue_event(
                    f"Fire cleared at {node_id}",
                    severity=1
                )
                return True
            return False
        
        if previous_level != 'none' and current_severity > previous_severity:
            if self._can_send(f"escalation_{node_id}", 300):
                temp = sensor_data.get('temperature', 0)
                smoke = sensor_data.get('smoke_density', 0)
                self._queue_event(
                    f"🔥 Fire escalated at {node_id}\nSeverity: {fire_level.upper()}\nTemp: {temp:.0f}°C\nSmoke: {smoke:.0f} ppm",
                    severity=current_severity
                )
                return True
            return False
        
        if fire_level != 'none' and previous_level == 'none':
            if self._can_send(f"fire_{node_id}", 30):
                temp = sensor_data.get('temperature', 0)
                smoke = sensor_data.get('smoke_density', 0)
                if fire_level == 'flashover':
                    self._send_with_retry(
                        "EVACUATION ALERT",
                        f"🔥 FLASHOVER at {node_id}\nTemp: {temp:.0f}°C\nSmoke: {smoke:.0f} ppm\n\nTime: {time.strftime('%H:%M:%S')}"
                    )
                    return True
                else:
                    self._queue_event(
                        f"🔥 Fire at {node_id}\nSeverity: {fire_level.upper()}\nTemp: {temp:.0f}°C\nSmoke: {smoke:.0f} ppm",
                        severity=current_severity
                    )
                    return True
        
        return False
    
    def process_route_update(self, route_info: Dict) -> bool:
        if not self.is_configured or not route_info:
            print("Route update failed: not configured or no route info")
            return False
        
        current_path = route_info.get('path', [])
        current_exit = current_path[-1] if current_path else None
        current_hazard_count = route_info.get('hazard_count', 0)
        current_cost = route_info.get('total_cost', 0)
        is_safe = route_info.get('is_safe', False)
        
        print(f"Route update: path={current_path[:3]}, exit={current_exit}, hazards={current_hazard_count}")
        
        route_changed = (current_path != self.last_route)
        exit_changed = (current_exit != self.last_exit)
        
        self.last_route = current_path
        self.last_exit = current_exit
        
        if not route_changed:
            print("Route unchanged, skipping notification")
            return False
        
        # Build a proper route message
        path_str = " → ".join(current_path[:5])
        if len(current_path) > 5:
            path_str += f" … → {current_exit}"
        
        status_text = "SAFE" if is_safe else f"⚠️ {current_hazard_count} HAZARDS"
        
        message = f"📍 ROUTE FROM {current_path[0] if current_path else 'Unknown'}\n"
        message += f"Exit: {current_exit}\n"
        message += f"Path: {path_str}\n"
        message += f"Nodes: {len(current_path)}\n"
        message += f"Cost: {current_cost:.2f}\n"
        message += f"Status: {status_text}\n"
        message += f"\nTime: {time.strftime('%H:%M:%S')}"
        
        print(f"Sending route notification: {message[:50]}...")
        
        event_id = self._generate_event_id('route', f"{str(current_path[:3])}_{current_exit}")
        
        # For exit changes, send immediately
        if exit_changed:
            if self._can_send(f"exit_{current_exit}", 0):
                return self._send_with_retry(
                    "EVACUATION ROUTE UPDATED",
                    message
                )
            return False
        
        # For normal route updates, queue or send based on cooldown
        if self._can_send("route", 60):
            self._queue_event(message, severity=1)
            return True
        
        print("Route update blocked by cooldown")
        return False
    
    def process_exit_change(self, node_id: str, is_blocked: bool) -> bool:
        if not self.is_configured:
            return False
        
        event_id = self._generate_event_id('exit', f"{node_id}_{is_blocked}")
        if self._is_duplicate(event_id):
            return False
        
        if is_blocked:
            if self._can_send_alert():
                self._send_with_retry(
                    "EVACUATION ALERT",
                    f"EXIT BLOCKED\nExit: {node_id}\nUse alternate route immediately.\n\nTime: {time.strftime('%H:%M:%S')}"
                )
                return True
            return False
        else:
            if self._can_send(f"exit_{node_id}", 0):
                self._queue_event(
                    f"Exit {node_id} is now OPEN",
                    severity=0
                )
                return True
        
        return False
    
    def process_critical_event(self, message: str, severity: int = 4) -> bool:
        if not self.is_configured:
            return False
        
        event_id = self._generate_event_id('critical', str(time.time()))
        if self._is_duplicate(event_id):
            return False
        
        if severity >= 3 and self._can_send_alert():
            self._send_with_retry(
                "EVACUATION ALERT",
                f"{message}\n\nTime: {time.strftime('%H:%M:%S')}"
            )
            return True
        
        if self._can_send("system", 120):
            self._queue_event(message, severity=severity)
            return True
        
        return False
    
    def _send_push(self, title: str, body: str) -> bool:
        return self._send_with_retry(title, body)
    
    def get_status(self) -> Dict:
        return {
            'is_configured': self.is_configured,
            'is_offline': self.is_offline,
            'offline_queue_size': len(self.offline_queue),
            'pending_events': len(self.pending_events),
            'last_sent_count': len(self.last_sent)
        }
    
    def start(self):
        logger.info("Pushbullet notifier ready")
    
    def stop(self):
        self._flush_events()
        if self.offline_queue:
            self.retry_offline_queue()
        logger.info("Pushbullet notifier stopped")