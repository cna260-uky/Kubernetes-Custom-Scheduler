import argparse
import time
import requests
import threading
import os
from queue import Queue

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--sleep', type=int, default=0, help='milliseconds to sleep')
parser.add_argument('--prime', type=int, default=0, help='calculate largest prime less than')
parser.add_argument('--bloat', type=int, default=0, help='MB of memory to consume')
parser.add_argument('--ip', type=str, default='', help='IP address of knative ingress')
parser.add_argument('--port', type=str, default='80', help='port of call')
parser.add_argument('--qps', type=int, default=10, help='max requests per second')
parser.add_argument('--concurrency', type=int, default=10, help='max in-flight requests')
parser.add_argument('--duration', type=int, default=60, help='duration of the test in seconds')
parser.add_argument('--timeout', type=int, default=10, help='timeout in seconds for low inflight requests')
parser.add_argument('--verbose', action='store_true', help='verbose output for debugging')
args = parser.parse_args()

# Global variables
stop_time = time.time() + args.duration
inflight = 0
total_requests = 0
successful_requests = 0
total_latency = 0
report_queue = Queue()
threads = []  # Store threads to manage them properly
low_inflight_start = None

# Function to send HTTP GET request
def get(url):
    global inflight, total_requests, successful_requests, total_latency
    start_time = time.time()
    try:
        response = requests.get(url)
        end_time = time.time()
        time.sleep(args.sleep / 1000)  # Simulate sleeping
        latency = int((end_time - start_time) * 1000000000)
        total_latency += latency
        total_requests += 1
        if response.status_code == 200:
            successful_requests += 1
            report_queue.put((True, latency))
        else:
            report_queue.put((False, latency))
    except Exception as e:
        if args.verbose:
            print(f"Error: {e}")
        total_requests += 1  # Count aborted or failed requests
        report_queue.put((False, 0))
    finally:
        with inflight_lock:
            inflight -= 1

# Function to collect and print statistics
def reporter():
    global total_requests, successful_requests, total_latency

    while time.time() < stop_time or inflight > 0:
        time.sleep(3)
        success_rate = (successful_requests / total_requests) * 100 if total_requests > 0 else 0
        avg_latency = (total_latency / total_requests) / 1e9 if total_requests > 0 else 0  # Convert nanoseconds to seconds
        print(f"Total: {total_requests} Inflight: {inflight} Success Rate: {success_rate:.2f}% Avg Latency: {avg_latency:.4f} sec")

# Main function to run load test
def load_test():
    global inflight, low_inflight_start, successful_requests

    ip_address = args.ip if args.ip else os.getenv("IP_ADDRESS")
    if not ip_address:
        raise ValueError("Either --ip flag or $IP_ADDRESS environment variable is required")
    url = f"http://{ip_address}:{args.port}?sleep={args.sleep}&prime={args.prime}&bloat={args.bloat}"

    while time.time() < stop_time:
        with inflight_lock:
            # Check if inflight requests are below concurrency and for how long
            if low_inflight_start is None:
                low_inflight_start = time.time()
                current_requests = successful_requests
            elif time.time() - low_inflight_start >= args.timeout:
                print("Low inflight requests for too long. Force ending.")
                break
            elif current_requests < successful_requests:
                low_inflight_start = None

        if inflight < args.concurrency:
            inflight += 1
            thread = threading.Thread(target=get, args=(url,))
            threads.append(thread)
            thread.start()
        time.sleep(1 / args.qps)  # Control the rate of requests

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Print final statistics
    success_rate = (successful_requests / total_requests) * 100 if total_requests > 0 else 0
    avg_latency = (total_latency / total_requests) / 1e9 if total_requests > 0 else 0
    print("\nFinal Statistics:")
    print(f"Total Requests: {total_requests}")
    print(f"Successful Requests: {successful_requests}")
    print(f"Success Rate: {success_rate:.2f}%")
    print(f"Average Latency: {avg_latency:.4f} sec")

if __name__ == "__main__":
    inflight_lock = threading.Lock()
    # Start the reporter thread
    threading.Thread(target=reporter, daemon=True).start()
    # Start the load test
    load_test()
