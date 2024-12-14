from math import sqrt
from flask import Flask, request, jsonify
import time
import threading

app = Flask(__name__)

def all_primes(N):
    nsqrt = int(sqrt(N))
    is_prime = [False] * (N + 1)

    for x in range(1, nsqrt + 1):
        for y in range(1, nsqrt + 1):
            n = 4 * (x * x) + y * y
            if n <= N and (n % 12 == 1 or n % 12 == 5):
                is_prime[n] = not is_prime[n]
            n = 3 * (x * x) + y * y
            if n <= N and n % 12 == 7:
                is_prime[n] = not is_prime[n]
            n = 3 * (x * x) - y * y
            if x > y and n <= N and n % 12 == 11:
                is_prime[n] = not is_prime[n]

    for n in range(5, nsqrt + 1):
        if is_prime[n]:
            for k in range(n * n, N + 1, n * n):
                is_prime[k] = False

    is_prime[2] = True
    is_prime[3] = True

    return [x for x in range(N + 1) if is_prime[x]]

def bloat(mb):
    b = bytearray(mb * 1024 * 1024)
    b[0] = 1
    b[-1] = 1
    return f"Allocated {mb} Mb of memory.\n"

def prime(max_val):
    primes = all_primes(max_val)
    if primes:
        return f"The largest prime less than {max_val} is {primes[-1]}.\n"
    else:
        return f"There are no primes smaller than {max_val}.\n"

def sleep(ms):
    start = time.time()
    time.sleep(ms / 1000.0)
    end = time.time()
    return f"Slept for {(end - start) * 1000:.2f} milliseconds.\n"

def parse_int_param(request, param):
    value = request.args.get(param)
    if value is not None:
        try:
            i = int(value)
            return i, i != 0
        except ValueError:
            return None, False
    return None, False

@app.route("/", methods=["GET"])
def handler():
    ms, has_ms = parse_int_param(request, "sleep")
    max_val, has_max = parse_int_param(request, "prime")
    mb, has_mb = parse_int_param(request, "bloat")

    responses = []
    threads = []

    def collect_response(func, *args):
        responses.append(func(*args))

    if has_ms:
        t = threading.Thread(target=collect_response, args=(sleep, ms))
        threads.append(t)
        t.start()
    if has_max:
        t = threading.Thread(target=collect_response, args=(prime, max_val))
        threads.append(t)
        t.start()
    if has_mb:
        t = threading.Thread(target=collect_response, args=(bloat, mb))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return "\n".join(responses)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)