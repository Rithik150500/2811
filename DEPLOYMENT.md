# Deployment Guide - Legal Risk Analysis Web Application

This guide covers deployment of the Legal Risk Analysis System web application in development, staging, and production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Development)](#quick-start-development)
3. [Environment Configuration](#environment-configuration)
4. [Production Deployment](#production-deployment)
5. [Docker Deployment](#docker-deployment)
6. [Security Considerations](#security-considerations)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **Python**: 3.10 or higher
- **RAM**: Minimum 4GB (8GB+ recommended for production)
- **Storage**: 10GB+ free space for data rooms and analysis outputs
- **OS**: Linux (Ubuntu 20.04+), macOS, or Windows with WSL2

### Required API Keys

You'll need an Anthropic API key to use Claude:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

Get your API key from: https://console.anthropic.com/

---

## Quick Start (Development)

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/legal-risk-analysis.git
cd legal-risk-analysis
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Environment Variables

Create a `.env` file in the project root:

```bash
# .env
ANTHROPIC_API_KEY=your-api-key-here
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### 5. Prepare Data Room

Ensure you have a preprocessed data room:

```bash
# If you need to preprocess documents
python legal_preprocessing_v2.py --input ./raw_data_room --output ./preprocessed_data_room
```

### 6. Run the Web Application

```bash
python web_app.py
```

The application will be available at: **http://localhost:8000**

---

## Environment Configuration

### Configuration File (.env)

Create a `.env` file with the following variables:

```bash
# API Configuration
ANTHROPIC_API_KEY=your-api-key-here
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929

# Server Configuration
HOST=0.0.0.0
PORT=8000
WORKERS=4
RELOAD=false

# Application Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
MAX_SESSIONS=100
SESSION_TIMEOUT=86400  # 24 hours in seconds

# Storage
OUTPUT_DIRECTORY=/var/lib/legal-analysis/outputs
DATA_ROOM_DIRECTORY=/var/lib/legal-analysis/data_rooms

# Security
SECRET_KEY=your-secret-key-here  # Generate with: openssl rand -hex 32
ALLOWED_ORIGINS=https://yourdomain.com

# Resource Limits
MAX_PAGE_IMAGES=50
MAX_WEB_FETCHES=20
MAX_ITERATIONS=50
```

### Environment-Specific Configurations

#### Development

```bash
ENVIRONMENT=development
LOG_LEVEL=DEBUG
RELOAD=true
WORKERS=1
```

#### Staging

```bash
ENVIRONMENT=staging
LOG_LEVEL=INFO
RELOAD=false
WORKERS=2
```

#### Production

```bash
ENVIRONMENT=production
LOG_LEVEL=WARNING
RELOAD=false
WORKERS=4
```

---

## Production Deployment

### Option 1: Systemd Service (Linux)

#### 1. Create Service File

Create `/etc/systemd/system/legal-analysis.service`:

```ini
[Unit]
Description=Legal Risk Analysis Web Application
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/legal-analysis
Environment="PATH=/opt/legal-analysis/venv/bin"
EnvironmentFile=/opt/legal-analysis/.env
ExecStart=/opt/legal-analysis/venv/bin/uvicorn web_app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level info

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 2. Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable legal-analysis

# Start service
sudo systemctl start legal-analysis

# Check status
sudo systemctl status legal-analysis

# View logs
sudo journalctl -u legal-analysis -f
```

### Option 2: Gunicorn with Nginx

#### 1. Install Gunicorn

```bash
pip install gunicorn
```

#### 2. Create Gunicorn Configuration

Create `gunicorn.conf.py`:

```python
import multiprocessing

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 300
keepalive = 2

# Logging
accesslog = "/var/log/legal-analysis/access.log"
errorlog = "/var/log/legal-analysis/error.log"
loglevel = "info"

# Process naming
proc_name = "legal-analysis"

# Server mechanics
daemon = False
pidfile = "/var/run/legal-analysis.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None
```

#### 3. Configure Nginx

Create `/etc/nginx/sites-available/legal-analysis`:

```nginx
upstream legal_analysis {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Max upload size
    client_max_body_size 100M;

    # Static files
    location /static {
        alias /opt/legal-analysis/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # WebSocket support
    location /ws {
        proxy_pass http://legal_analysis;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    # API and application
    location / {
        proxy_pass http://legal_analysis;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
    }
}
```

#### 4. Enable Nginx Site

```bash
# Link configuration
sudo ln -s /etc/nginx/sites-available/legal-analysis /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

#### 5. Start Gunicorn

```bash
gunicorn -c gunicorn.conf.py web_app:app
```

---

## Docker Deployment

### 1. Create Dockerfile

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p templates static/css static/js

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "web_app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 2. Create docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    container_name: legal-analysis-web
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    volumes:
      - ./preprocessed_data_room:/app/preprocessed_data_room:ro
      - ./analysis_output:/app/analysis_output
      - ./logs:/var/log/legal-analysis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    container_name: legal-analysis-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./static:/var/www/static:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - web
    restart: unless-stopped
```

### 3. Build and Run

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## Security Considerations

### 1. API Key Security

- **Never** commit API keys to version control
- Use environment variables or secret management systems
- Rotate API keys regularly
- Limit API key permissions

### 2. Authentication & Authorization

For production, implement authentication:

```python
# Add to web_app.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Implement your authentication logic
    if credentials.credentials != os.getenv("API_TOKEN"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return credentials.credentials

# Protect routes
@app.get("/api/sessions", dependencies=[Depends(verify_token)])
async def list_sessions():
    # ...
```

### 3. CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
```

### 4. Rate Limiting

```bash
pip install slowapi
```

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/analysis/start")
@limiter.limit("5/minute")
async def start_analysis(request: Request):
    # ...
```

---

## Monitoring & Maintenance

### Application Monitoring

#### Health Checks

```bash
# Check application health
curl http://localhost:8000/health

# Expected response
{"status":"healthy","active_sessions":0,"timestamp":"2025-01-15T10:30:00"}
```

#### Logging

Monitor logs for errors and performance:

```bash
# Follow application logs
tail -f /var/log/legal-analysis/error.log

# Monitor access patterns
tail -f /var/log/legal-analysis/access.log
```

### Resource Monitoring

Monitor system resources:

```bash
# CPU and memory usage
htop

# Disk usage
df -h

# Docker stats
docker stats
```

### Backup Strategy

Regular backups of:

1. **Analysis outputs**: `/var/lib/legal-analysis/outputs`
2. **Session data**: Checkpoint state
3. **Configuration**: `.env` and config files

```bash
# Backup script example
#!/bin/bash
BACKUP_DIR="/backups/legal-analysis/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup outputs
tar -czf "$BACKUP_DIR/outputs.tar.gz" /var/lib/legal-analysis/outputs

# Backup config (excluding secrets)
cp /opt/legal-analysis/*.py "$BACKUP_DIR/"
```

---

## Troubleshooting

### Common Issues

#### 1. Application Won't Start

```bash
# Check Python version
python --version  # Should be 3.10+

# Verify dependencies
pip list | grep fastapi

# Check port availability
sudo netstat -tulpn | grep 8000
```

#### 2. WebSocket Connection Failures

- Verify Nginx WebSocket proxy configuration
- Check firewall rules for WebSocket ports
- Ensure `Connection: upgrade` header is set

#### 3. High Memory Usage

- Reduce worker count
- Implement session cleanup
- Limit concurrent analyses

#### 4. Slow Performance

- Increase worker processes
- Enable caching
- Optimize database queries (if added)
- Use CDN for static assets

### Debug Mode

Enable debug mode for troubleshooting:

```bash
# Set environment
export LOG_LEVEL=DEBUG
export ENVIRONMENT=development

# Run with reload
uvicorn web_app:app --reload --log-level debug
```

### Getting Help

- Check logs: `/var/log/legal-analysis/`
- Review systemd status: `sudo systemctl status legal-analysis`
- Test API endpoints: `curl -v http://localhost:8000/health`
- Check Docker logs: `docker-compose logs -f`

---

## Scaling Considerations

### Horizontal Scaling

For high-traffic environments:

1. **Load Balancer**: Use Nginx/HAProxy to distribute traffic
2. **Multiple Workers**: Increase Gunicorn/Uvicorn workers
3. **Session Storage**: Migrate from in-memory to Redis/PostgreSQL
4. **File Storage**: Use S3 or similar for analysis outputs

### Vertical Scaling

- Increase RAM for larger data rooms
- Add CPU cores for parallel processing
- Faster SSD storage for I/O operations

---

## Maintenance Schedule

### Daily
- Monitor error logs
- Check disk space
- Verify backup completion

### Weekly
- Review application performance
- Clean up old sessions
- Update security patches

### Monthly
- Rotate API keys
- Update dependencies
- Performance optimization review

---

## Support & Documentation

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **System Architecture**: See `CLAUDE.md`
- **Issues**: Report at GitHub repository

---

**Last Updated**: 2025-01-15
**Version**: 1.0.0
