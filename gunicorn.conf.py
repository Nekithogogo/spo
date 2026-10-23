# Настройки gunicorn для тестового окружения.
bind = "0.0.0.0:8000"
workers = 2
timeout = 30
accesslog = "-"   # журнал запросов в stdout -> docker logs
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms'
