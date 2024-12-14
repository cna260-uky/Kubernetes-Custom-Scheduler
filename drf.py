import time
import requests
from kubernetes import client, config

# Configure Kubernetes client
config.load_kube_config()
v1 = client.CoreV1Api()

SERVER = "http://localhost:8001"
NAMESPACE = "workload"
SCHEDULER_NAME = "drf"

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
        cpu = int(allocatable["cpu"].strip("m"))*1000  # CPU in millicores
        memory = int(allocatable["memory"].strip("Ki")) // 1024  # Memory in MiB
        available_nodes.append({"name": node.metadata.name, "available_cpu": cpu, "available_memory": memory})
    return available_nodes

def update_node_info(available_nodes, pod_name, node_name):
    """
    Update the available resources of a specific node after scheduling a pod.
    """
    pod = v1.read_namespaced_pod(pod_name, NAMESPACE)
    resources = pod.spec.containers[0].resources.requests
    pod_cpu = int(resources["cpu"].strip("m"))  # CPU in millicores
    pod_memory = int(resources["memory"].strip("Mi"))  # Memory in MiB

    for node in available_nodes:
        if node["name"] == node_name:
            node["available_cpu"] -= pod_cpu
            node["available_memory"] -= pod_memory
            break
    return available_nodes

def drf(unscheduled_pods, available_nodes):
    """
    DRF (Dominant Resource Fairness) scheduling algorithm.
    This function places pods on nodes according to the DRF algorithm.
    """
    # Find total resource capacities
    if not available_nodes:
        return

    total_cpu = sum(node["available_cpu"] for node in available_nodes)
    total_memory = sum(node["available_memory"] for node in available_nodes)

    while unscheduled_pods:
        if not available_nodes:
            print("No available nodes with sufficient resources.")
            break
        # print(f"unscheduled pods: {unscheduled_pods}")
        # print(f"available nodes: {available_nodes}")
        pod_drs = []
        for pod_name in unscheduled_pods:
            # Get resource requests
            pod = v1.read_namespaced_pod(pod_name, NAMESPACE)
            resources = pod.spec.containers[0].resources.requests
            pod_cpu = int(resources["cpu"].strip("m"))  # CPU in millicores
            pod_memory = int(resources["memory"].strip("Mi"))  # Memory in MiB
            # Find DRS
            drs_cpu = pod_cpu / total_cpu if total_cpu else float('inf')
            drs_memory = pod_memory / total_memory if total_memory else float('inf')
            drs = max(drs_cpu, drs_memory)  # Dominant resource share
            drs_resource = "cpu" if drs_cpu > drs_memory else "memory"
            pod_drs.append({"pod_name": pod_name, "pod_cpu": pod_cpu, "pod_memory": pod_memory, "drs": drs, "drs_resource": drs_resource})
        # Find minimum DRS
        pod_drs.sort(key=lambda p: p["drs"])
        chosen_pod = pod_drs[0]
        # print(f"chosen pod: {chosen_pod}")
        # Select the node with maximum available resource
        if chosen_pod["drs_resource"] == "cpu":
            chosen_node = max(available_nodes, key=lambda node: node['available_cpu'])   
            if chosen_node["available_cpu"] < chosen_pod["pod_cpu"]:
                chosen_node = None
        else:
            chosen_node = max(available_nodes, key=lambda node: node["available_memory"])
            if chosen_node["available_memory"] < chosen_pod["pod_memory"]:
                chosen_node = None
        if chosen_node is None:
            print(f"Unable to schedule pod {chosen_pod['pod_name']} due to insufficient resources.")
            unscheduled_pods.remove(chosen_pod["pod_name"])
            continue
        else:
            bind_pod_to_node(chosen_pod['pod_name'], chosen_node['name'])
            available_nodes = update_node_info(available_nodes, chosen_pod['pod_name'], chosen_node['name'])

        # Remove scheduled pod from list
        unscheduled_pods.remove(chosen_pod["pod_name"])

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

        # Schedule each pod to a random node
        drf(unscheduled_pods, available_nodes)

        # Wait before the next iteration
        time.sleep(1)

if __name__ == "__main__":
    main()
