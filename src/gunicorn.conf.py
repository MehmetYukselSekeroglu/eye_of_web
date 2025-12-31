# Gunicorn configuration file for EyeOfWeb
import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('FLASK_PORT', 5000)}"
backlog = 2048

# Worker processes
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = "gthread"
threads = int(os.environ.get('GUNICORN_THREADS', 4))
worker_connections = 1000
max_requests = 1000  # Restart worker after this many requests
max_requests_jitter = 100  # Add randomness to max_requests

# Timeout settings
timeout = 120
keepalive = 2
graceful_timeout = 30

# Memory management
preload_app = True  # Load application code before forking worker processes

# SSL Configuration (if certificates exist)
if os.path.exists('certs/cert.pem') and os.path.exists('certs/key.pem'):
    keyfile = 'certs/key.pem'
    certfile = 'certs/cert.pem'
    ssl_version = 2  # TLSv1_2

# Logging
if not os.path.exists('logs'):
    os.makedirs('logs')

accesslog = 'logs/gunicorn_access.log'
errorlog = 'logs/gunicorn_error.log'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'eyeofweb'

# Restart workers after memory usage
max_worker_memory = 512 * 1024 * 1024  # 512MB

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance
sendfile = True
reuse_port = True if hasattr(__import__('socket'), 'SO_REUSEPORT') else False

# Development vs Production
debug = os.environ.get('FLASK_ENV', 'production') == 'development'

# Worker lifecycle hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("EyeOfWeb is starting...")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("EyeOfWeb is reloading...")

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info(f"Worker {worker.pid} is being forked")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info(f"Worker {worker.pid} has been forked")

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info(f"Worker {worker.pid} received SIGABRT signal")

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("EyeOfWeb is ready. Workers have been spawned.")

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    server.log.info(f"Worker {worker.pid} exited")

def nworkers_changed(server, new_value, old_value):
    """Called just after num_workers has been changed."""
    server.log.info(f"Number of workers changed from {old_value} to {new_value}")

# Environment variables
raw_env = [
    'FLASK_ENV=' + os.environ.get('FLASK_ENV', 'production'),
    'PYTHONPATH=' + os.environ.get('PYTHONPATH', ''),
] 