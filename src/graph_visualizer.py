import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch
import networkx as nx
from typing import Dict, List, Tuple, Any
import io
import base64


class GraphVisualizer:
    
    def __init__(self, engine):
        self.engine = engine
    
    def create_route_figure(self, start_node: str, route_info: Dict) -> plt.Figure:
        fig, ax = plt.subplots(figsize=(8, 6), dpi=120)
        ax.set_facecolor('#f8f9fa')
        pos = self.engine.node_positions
        G = nx.Graph()
        for node in self.engine.nodes:
            node_id = node['id']
            G.add_node(node_id, pos=pos.get(node_id, (0, 0)))
            for conn in node.get('connections', []):
                weight = self.engine.graph.get(node_id, {}).get(conn, 1.0)
                G.add_edge(node_id, conn, weight=weight)
        pos_dict = {node_id: pos.get(node_id, (0, 0)) for node_id in G.nodes()}
        node_colors = []
        for node in G.nodes():
            weight = self.engine.node_weights.get(node, 1.0)
            if weight == float('inf'):
                node_colors.append('#000000')
            elif weight > 10.0:
                node_colors.append('#ff0000')
            elif weight > 5.0:
                node_colors.append('#ff8c00')
            elif weight > 2.0:
                node_colors.append('#ffd700')
            else:
                node_colors.append('#00cc44')
        node_sizes = []
        for node in G.nodes():
            if node in self.engine.exits:
                node_sizes.append(600)
            else:
                node_sizes.append(350)
        nx.draw_networkx_nodes(G, pos_dict, 
                              node_color=node_colors,
                              node_size=node_sizes,
                              ax=ax,
                              edgecolors='#333333',
                              linewidths=2)
        edge_colors = []
        edge_widths = []
        for u, v, data in G.edges(data=True):
            weight = data.get('weight', 1.0)
            if weight == float('inf'):
                edge_colors.append('#ff0000')
                edge_widths.append(3)
            elif weight > 5.0:
                edge_colors.append('#ff8c00')
                edge_widths.append(2)
            elif weight > 2.0:
                edge_colors.append('#ffd700')
                edge_widths.append(1.5)
            else:
                edge_colors.append('#808080')
                edge_widths.append(1)
        
        for i, ((u, v), color, width) in enumerate(zip(G.edges(), edge_colors, edge_widths)):
            nx.draw_networkx_edges(G, pos_dict,
                                  edgelist=[(u, v)],
                                  edge_color=color,
                                  width=width,
                                  ax=ax,
                                  alpha=0.8)
        labels = {}
        for node in G.nodes():
            label = node
            if node in self.engine.exits:
                label = f"{node}\n🚪"
            labels[node] = label
        
        nx.draw_networkx_labels(G, pos_dict, labels, 
                               font_size=8,
                               font_weight='bold',
                               ax=ax)
        if route_info and 'path' in route_info:
            path = route_info['path']
            path_nodes = [(path[i], path[i+1]) for i in range(len(path)-1)]
            if path_nodes:
                nx.draw_networkx_edges(G, pos_dict,
                                      edgelist=path_nodes,
                                      edge_color='#00ff00',
                                      width=5,
                                      ax=ax,
                                      alpha=0.9)
                for i, (u, v) in enumerate(path_nodes):
                    if i % 2 == 0:
                        x1, y1 = pos_dict[u]
                        x2, y2 = pos_dict[v]
                        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                                   arrowprops=dict(arrowstyle='->',
                                                 color='#00ff00',
                                                 lw=3,
                                                 alpha=0.8))
                start = path[0]
                end = path[-1]
                nx.draw_networkx_nodes(G, pos_dict,
                                      nodelist=[start],
                                      node_color='#00ff00',
                                      node_shape='s',
                                      node_size=500,
                                      ax=ax)
                ax.annotate('START', 
                           xy=pos_dict[start],
                           xytext=(pos_dict[start][0], pos_dict[start][1] - 30),
                           ha='center',
                           fontweight='bold',
                           color='green',
                           fontsize=10,
                           ax=ax)
                if end in self.engine.exits:
                    nx.draw_networkx_nodes(G, pos_dict,
                                          nodelist=[end],
                                          node_color='#0066cc',
                                          node_shape='s',
                                          node_size=500,
                                          ax=ax)
                    ax.annotate('EXIT', 
                               xy=pos_dict[end],
                               xytext=(pos_dict[end][0], pos_dict[end][1] - 30),
                               ha='center',
                               fontweight='bold',
                               color='blue',
                               fontsize=10,
                               ax=ax)

        legend_elements = [
            patches.Patch(facecolor='#00cc44', label='Safe Node', alpha=0.8),
            patches.Patch(facecolor='#ffd700', label='Warning Node', alpha=0.8),
            patches.Patch(facecolor='#ff8c00', label='Danger Node', alpha=0.8),
            patches.Patch(facecolor='#ff0000', label='Critical Node', alpha=0.8),
            patches.Patch(facecolor='#000000', label='Blocked Node', alpha=0.8),
            patches.Patch(facecolor='#0066cc', label='Exit', alpha=0.8),
            patches.Patch(facecolor='#00ff00', label='Route Path', alpha=0.8),
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=8)
        ax.set_title(f'🔥 Evacuation Route from {start_node}\n'
                    f'Length: {route_info["path_length"]} nodes | '
                    f'Cost: {route_info["total_cost"]:.2f} | '
                    f'Status: {"✅ SAFE" if route_info["is_safe"] else "⚠️ HAZARDS"}',
                    fontsize=11, fontweight='bold')
        
        ax.axis('off')
        ax.set_aspect('equal')
        info_text = f"Safe Nodes: {route_info['safe_nodes']}\n"
        info_text += f"Hazard Nodes: {route_info['hazard_count']}\n"
        info_text += f"Compute Time: {route_info['computation_time_ms']:.1f}ms"
        
        ax.text(0.02, 0.98, info_text,
               transform=ax.transAxes,
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.9),
               fontsize=9)
        
        plt.tight_layout()
        return fig
    
    def save_route_image(self, start_node: str, route_info: Dict, 
                         filename: str = None) -> str:
        fig = self.create_route_figure(start_node, route_info)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        if filename:
            fig.savefig(filename, dpi=300, bbox_inches='tight')
        return image_base64