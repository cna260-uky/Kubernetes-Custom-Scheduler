# Kubernetes Custom Scheduler

An experiment on implementing a custom scheduler using Python and the Kubernetes API.

## Prerequisites

1. A Kubernetes cluster set up in CloudLabs with at least 2 external IP addresses configured.
2. Prometheus and Grafana installed (Can follow these steps: https://gitlab.com/nanuchi/youtube-tutorial-series/-/blob/master/prometheus-exporter/install-prometheus-commands.md).
3. Install [Docker](https://docs.docker.com/get-started/#prepare-your-docker-environment).

## Setup

Build the application container and publish it to a container registry:

1. Move into a sample directory, where your main.py file and Dockerfile exists. 

2. Containerize the python code:
   ```
   docker build -f Dockerfile -t <name of folder main.py>:latest .
   ```
   * This example shows how to use a private registry in the Kubernetes cluster. You will need to set insecure registries both in the cluster nodes in this file:
   ```
   /etc/systemd/system/docker.service.d/docker-options.conf
   ```
   * And in your local DockerHub, which on Windows can be found in Docker Desktop --> Settings --> Docker Engine, and adding the line:
   ```
   "insecure-registries": ["<private registry IP>:<outward facing port>"]
   ```
3. Initialize the private registry in the Kubernetes cluster.
   * On the master node, run the following command to access the private registry. From here on, the Docker port will be 5001.
   ```
   docker run -d --restart=always --name registry -v /mnt/registry-data:/var/lib/registry -p 5001:5000 registry:2
   ```
5. Use Docker to tag your application container:
   ```
   docker tag <name of application folder>:latest <control node IP>:5001/<name of application folder>:latest
   ```

6. Push your container to a container registry:
   ```  
   docker push <control node IP>:5001/<name of application folder>:latest
   ```

## Deploy the Service

1. Pull the image in the cluster:
   ```
   docker pull <control node IP>:5001/<name of application folder>:latest
   ```

2. Use the deployment file for the workload:
   ```
   kubectl apply -f wl-setup.yaml
   kubectl apply -f wl-hpa.yaml
   ```
   * Optional: you can create a namespace to keep the workload deployments separated if you will be running many applications.
   ```
   kubectl create namespace workload
   kubectl apply -f wl-setup.yaml -n workload
   kubectl apply -f wl-hpa.yaml -n workload
   ```

## View the application working.

1. Make a request to the containerized app to see its response. Get the external IP address of the service using
   ```
   kubectl get service -n workload
   ```
   And look for the external IP address.
   ```
   curl "http://<external IP address of service>?sleep=100&prime=10000&bloat=5"
   ```
   ```
   Allocated 5 Mb of memory.
   The largest prime less than 10000 is 9973.
   Slept for 100.13 milliseconds.
   ```

2. Use the automatic 'send_requests.py' script to ramp up traffic to maintain 20 in-flight requests, at 20 queries per second. This file can be located at your local machine.

   ```
   python send_requests.py --ip 128.105.146.155 --port 6060 --qps 20 --concurrency 20 --duration 120 --prime 100000 --bloat 5 --sleep 500
   ```
   ```
   Total: 3 Inflight: 20 Success Rate: 100.00% Avg Latency: 0.9154 sec
   Total: 5 Inflight: 20 Success Rate: 100.00% Avg Latency: 2.3515 sec
   Total: 7 Inflight: 20 Success Rate: 100.00% Avg Latency: 3.7279 sec
   ...
   Total: 580 Inflight: 3 Success Rate: 98.10% Avg Latency: 3.1911 sec
   Total: 581 Inflight: 2 Success Rate: 98.11% Avg Latency: 3.1919 sec

   Final Statistics:
   Total Requests: 583
   Successful Requests: 572
   Success Rate: 98.11%
   Average Latency: 3.2346 sec
   ```
   * Use the following command to watch new pods being creating and scheduled.
   ```
   kubectl get pods -n workload --watch
   ```
   ```
   kubectl get pods -n workload --watch
   NAME                              READY   STATUS    RESTARTS   AGE
   wl-deployment-5966849d9-6wlw9     1/1     Running   0          39s
   wl-deployment2-54447b8957-p9m28   1/1     Running   0          36s
   wl-deployment-5966849d9-g9rmp     0/1     Pending   0          0s
   wl-deployment-5966849d9-q5kzl     0/1     Pending   0          0s
   ```
3. To use a different scheduler, modify the deployment file under 'schedulerName', and reapply it. Then start the kubectl proxy server and the scheduler in different terminals. Then send more requests to the service.
   ```
   kubectl proxy
   ```
   ```
   python3 <scheduler name>.py
   ```


## View the Knative Serving Scaling and Request dashboards (if configured).

1. Change the configuration of Grafana to give it an external IP address.
   ```
   kubectl patch svc prometheus-grafana -p '{"spec":{"type":"LoadBalancer"}}'

   ```
2. Access the Grafana UI at: http://<external-IP of Grafana service>:80
3. Go to Dashboards, create a new dashboard, and enter the following queries to see the number of desired and active pods over time.
   ```
   count(kube_pod_container_status_running{container="wl-container"})
   kube_horizontalpodautoscaler_status_desired_replicas{horizontalpodautoscaler="wl-hpa"}

   ```


## Cleanup

1. To delete the application deployments, run the following commands.
   ```
   kubectl delete -f wl-setup.yaml
   kubectl delete -f wl-setup2.yaml
   kubectl delete -f wl-hpa.yaml
   kubectl delete -f wl-hpa2.yaml
   ```
