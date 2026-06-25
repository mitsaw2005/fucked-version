import os
import multiprocessing

workers = int(os.getenv('WEB_CONCURRENCY', multiprocessing.cpu_count() * 2 + 1))
bind = os.getenv('WEB_BIND', '0.0.0.0:8000')
loglevel = 'info'
accesslog = '-'
errorlog = '-'
