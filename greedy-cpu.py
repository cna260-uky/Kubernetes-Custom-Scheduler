import time
import requests
from kubernetes import client, config

# Configure Kubernetes client
config.load_kube_config()
v1 = client.CoreV1Api()

SERVER = "http://localhost:8001"
NAMESPACE = "workload"
SCHEDULER_NAME = "greedy-cpu"

def get_unscheduled_pods():
    """
    Get the list of pods in the specified namespace that are unscheduled
    and use the custom scheduler.
    """
    pods = v1.list_namespaced_pod(NAMESPACE)
    unscheduled_pods = [
        pod.metadata.name
        for pod in pods.items
        if pod.spec.scheduler_name == SCHEDULER_NAME and not pod.spec.node_name
    ]
    return unscheduled_pods

def get_available_nodes():
    """
    Get the list of available nodes and their resource usage, excluding 'node-0'.
    Returns a list of dictionaries with node name, available CPU, and available memory.
    """
    nodes = v1.list_node()
    available_nodes = []
    for node in nodes.items:
        if node.metadata.name == "node-0":
            continue
        # Retrieve resource information
        allocatable = node.status.allocatable
        cpu = int(allocatable["cpu"].strip("m"))  # CPU in millicores
        memory = int(allocatable["memory"].strip("Ki")) // 1024  # Memory in MiB
        available_nodes.append({"name": node.metadata.name, "available_cpu": cpu, "available_memory": memory})
    return available_nodes

def greedy_choice_cpu(available_nodes):
    """
    Choose the node with the most available CPU.
    """
    if not available_nodes:
        return None
    # Select the node with maximum available CPU
    return max(available_nodes, key=lambda node: node['available_cpu'])

def bind_pod_to_node(pod_name, node_name):
    """
    Bind a pod to a specific node.
    """
    url = f"{SERVER}/api/v1/namespaces/{NAMESPACE}/pods/{pod_name}/binding/"
    binding = {
        "apiVersion": "v1",
        "kind": "Binding",
        "metadata": {"name": pod_name},
        "target": {"apiVersion": "v1", "kind": "Node", "name": node_name},
    }
    response = requests.post(url, json=binding)
    if response.status_code == 201:
        print(f"Successfully assigned {pod_name} to {node_name}")
    else:
        print(f"Failed to assign {pod_name} to {node_name}: {response.text}")

def main():
    while True:
        # Get unscheduled pods and available nodes
        unscheduled_pods = get_unscheduled_pods()
        available_nodes = get_available_nodes()

        if not available_nodes:
            print("No available nodes for scheduling.")
            time.sleep(1)
            continue

        # Schedule each pod to the best node based on CPU or memory
        for pod_name in unscheduled_pods:
            # Use the desired greedy_choice function
            chosen_node = greedy_choice_cpu(available_nodes)

            if chosen_node:
                bind_pod_to_node(pod_name, chosen_node['name'])
                # Update node resources after scheduling
                available_nodes = get_available_nodes()

        # Wait before the next iteration
        time.sleep(1)

if __name__ == "__main__":
    main()
