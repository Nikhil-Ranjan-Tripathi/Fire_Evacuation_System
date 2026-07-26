# 1. Project Title

```text
# AI-Based Smart Fire Evacuation System
```

**One-line description**

> An intelligent fire evacuation system that calculates the safest evacuation route using real-time sensor data, graph algorithms, and dynamic risk analysis.

---

# 2. Project Overview

Write 1–2 short paragraphs.

Example:

> This project simulates an intelligent indoor fire evacuation system capable of dynamically generating the safest evacuation route during fire emergencies. Instead of relying on static exit maps, the system continuously monitors simulated sensor data, evaluates fire severity, and recalculates routes in real time using graph-based pathfinding algorithms.

> The system also provides live visualisation through a dashboard and sends emergency notifications using Pushbullet.

---

# 3. System Architecture

Use a simple flowchart.

```text
                    ┌──────────────────────┐
                    │   Fire Injection     │
                    └──────────┬───────────┘
                               │
                    ┌──────────────────────┐
                    │  Sensor Simulator    │
                    └──────────┬───────────┘
                               │
                    ┌──────────────────────┐
                    │   Risk Calculation   │
                    └──────────┬───────────┘
                               │
                    ┌──────────────────────┐
                    │   Routing Engine     │
                    │   (A* Algorithm)     │
                    └──────────┬───────────┘
                               │
              ┌────────────────┴──────────────┐
     ┌─────────────────┐             ┌─────────────────┐
     │ GUI Dashboard   │             │ Pushbullet      │
     │ Route Display   │             │ Notifications   │
     └─────────────────┘             └─────────────────┘
```

---

# 4. Project Structure

```text
fire_evacuation_router/

│
├── data/
│   ├── building_grid.json
│   ├── sensor_data.json
│   └── pushbullet_config.json
│
├── src/
│   ├── gui_dashboard.py
│   ├── routing_engine.py
│   ├── sensor_simulator.py
│   ├── pushbullet_notifier.py
│   └── ...
│
├── assets/
│
├── run_system.py
│
└── README.md
```

---

# 5. Technology Stack

| Category              | Technology                  |
| --------------------- | --------------------------- |
| Programming Language  | Python 3                    |
| GUI Framework         | Tkinter                     |
| Pathfinding Algorithm | A* Search                   |
| Data Storage          | JSON                        |
| Notification Service  | Pushbullet API              |
| Graph Representation  | Adjacency List              |
| Architecture          | Object-Oriented Programming |

---

# 6. Modules

Explain each file in 2–3 lines.

### `routing_engine.py`

* Builds the building graph.
* Calculates node risk.
* Uses the A* algorithm to determine the safest evacuation path.
* Updates routes whenever fire conditions change.

---

### `sensor_simulator.py`

* Simulates smoke, temperature and flame sensors.
* Generates dynamic sensor readings.
* Updates node conditions continuously.

---

### `gui_dashboard.py`

* Displays the building layout.
* Allows fire injection.
* Shows evacuation routes.
* Displays sensor information in real time.

---

### `pushbullet_notifier.py`

* Sends emergency notifications.
* Reduces duplicate alerts using cooldowns.
* Batches non-critical notifications.
* Supports route and status updates.

---

# 7. Working Flow

Another flowchart.

```text
User Selects Start Node
            │
Fire Injected
            │
Sensor Values Updated
            │
Risk Levels Calculated
            │
Graph Edge Costs Updated
            │
A* Finds Safest Route
            │
GUI Updated
            │
Notification Sent
```

---

# 8. Routing Algorithm

Explain it briefly.

```text
Current Position

↓

Calculate Risk

↓

Update Graph Weights

↓

A* Search

↓

Safest Exit

↓

Display Route
```

Mention:

* Uses A* Search.
* Risk-aware movement cost.
* Dynamically avoids hazardous nodes.
* Falls back to the least hazardous path if no completely safe route exists.

---

# 9. Fire Severity Model

| Fire Level | Behaviour                        |
| ---------- | -------------------------------- |
| Normal     | Safe to traverse                 |
| Low        | Traversable with additional cost |
| Medium     | Avoid if possible                |
| High       | Strongly discouraged             |
| Flashover  | Blocked                          |

---

# 10. Notification Workflow

```text
Fire Event
      │
Notification Manager
      │
      ├── Duplicate Detection
      ├── Cooldown Check
      ├── Event Batching
      └── Severity Check
      │
Pushbullet
      │
Mobile Device
```

---

# 11. Future Scope

Keep it short.

* Multi-floor building support
* Real IoT sensor integration
* Mobile application
* Voice-guided evacuation
* Cloud-based monitoring

---

## Final structure

```text
README

│
├── Project Title
├── Project Overview
├── System Architecture
├── Project Structure
├── Technology Stack
├── Module Description
├── Working Flow
├── Routing Algorithm
├── Fire Severity Model
├── Notification Workflow
├── Installation
└── Future Scope
```
