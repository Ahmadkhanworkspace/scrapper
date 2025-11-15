# 🚀 Deployment Guide - E-commerce Scraper Admin Panel

## ❌ Why NOT Vercel?

**Vercel is NOT suitable for this project** because:

1. **Execution Time Limits**: Vercel functions have 10-second (free) or 60-second (pro) limits
   - Your scraper runs for minutes, not seconds
   - Playwright browser automation takes time

2. **Playwright Dependencies**: Playwright requires system-level dependencies (browsers, libraries)
   - Vercel serverless functions don't support this
   - No way to install Chromium/Firefox browsers

3. **SQLite Database**: Your app uses file-based SQLite (`admin_panel.db`)
   - Serverless functions are stateless
   - File system is read-only except `/tmp` (which gets cleared)

4. **WebSocket Support**: Flask-SocketIO needs persistent connections
   - Vercel has limited WebSocket support
   - Not ideal for real-time updates

5. **Long-Running Processes**: Background threads and scraping jobs
   - Serverless functions are request-based
   - No support for background tasks

---

## ✅ Recommended Deployment Platforms

### 🥇 **1. Railway** (BEST CHOICE - Easiest)

**Why Railway?**
- ✅ One-click deployment from GitHub
- ✅ Automatic PostgreSQL database
- ✅ Supports Playwright and browser automation
- ✅ Persistent file storage
- ✅ WebSocket support
- ✅ Free tier available ($5 credit/month)
- ✅ Easy environment variables

**Deployment Steps:**

1. **Create Railway Account**
   - Go to https://railway.app
   - Sign up with GitHub

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your GitHub account
   - Select repository: `aqstoria/Amazon-Scraper`

3. **Add PostgreSQL Database**
   - In Railway dashboard, click "+ New"
   - Select "Database" → "PostgreSQL"
   - Railway will provide connection string automatically

4. **Configure Environment Variables**
   - In your project settings, add these:
   ```
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   FLASK_ENV=production
   PORT=5000
   ```

5. **Create `Procfile`** (for Railway to know how to start)
   ```
   web: python admin_panel.py
   ```

6. **Update `requirements.txt`** - Add Playwright:
   ```
   playwright==1.40.0
   ```

7. **Create `railway.json`** (optional, for build config):
   ```json
   {
     "$schema": "https://railway.app/railway.schema.json",
     "build": {
       "builder": "NIXPACKS"
     },
     "deploy": {
       "startCommand": "python admin_panel.py",
       "restartPolicyType": "ON_FAILURE",
       "restartPolicyMaxRetries": 10
     }
   }
   ```

8. **Update Database Connection** in `admin_panel.py`:
   ```python
   import os
   DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///admin_panel.db')
   # If DATABASE_URL is set, use PostgreSQL instead of SQLite
   ```

9. **Deploy**
   - Railway will auto-detect Python
   - Install dependencies from `requirements.txt`
   - Run `playwright install chromium` during build
   - Deploy automatically on every push to main branch

**Cost**: Free tier ($5 credit/month), then $5/month for basic plan

---

### 🥈 **2. Render** (Similar to Railway)

**Why Render?**
- ✅ Free tier available
- ✅ PostgreSQL database included
- ✅ Auto-deploy from GitHub
- ✅ Supports Docker
- ✅ Persistent disk storage

**Deployment Steps:**

1. **Create Render Account**
   - Go to https://render.com
   - Sign up with GitHub

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect GitHub repo: `aqstoria/Amazon-Scraper`

3. **Configure Build Settings**
   - **Build Command**: `pip install -r requirements.txt && playwright install chromium`
   - **Start Command**: `python admin_panel.py`
   - **Environment**: Python 3

4. **Add PostgreSQL Database**
   - Click "New +" → "PostgreSQL"
   - Copy the connection string
   - Add as environment variable: `DATABASE_URL`

5. **Set Environment Variables**
   ```
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=<from-postgres-service>
   FLASK_ENV=production
   PORT=5000
   ```

6. **Deploy**
   - Render will build and deploy automatically
   - First deploy takes ~5-10 minutes

**Cost**: Free tier (spins down after 15 min inactivity), $7/month for always-on

---

### 🥉 **3. Fly.io** (Good for Docker)

**Why Fly.io?**
- ✅ Docker-based deployment
- ✅ Global edge network
- ✅ PostgreSQL support
- ✅ Good for scaling

**Deployment Steps:**

1. **Install Fly CLI**
   ```bash
   powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
   ```

2. **Create `Dockerfile`**:
   ```dockerfile
   FROM python:3.11-slim

   # Install system dependencies for Playwright
   RUN apt-get update && apt-get install -y \
       wget \
       gnupg \
       && rm -rf /var/lib/apt/lists/*

   WORKDIR /app

   # Copy requirements
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   # Install Playwright browsers
   RUN pip install playwright
   RUN playwright install chromium
   RUN playwright install-deps chromium

   # Copy application
   COPY . .

   # Expose port
   EXPOSE 5000

   # Run application
   CMD ["python", "admin_panel.py"]
   ```

3. **Create `fly.toml`**:
   ```toml
   app = "your-app-name"
   primary_region = "iad"

   [build]

   [env]
     PORT = "5000"

   [[services]]
     internal_port = 5000
     protocol = "tcp"

     [[services.ports]]
       handlers = ["http"]
       port = 80
       force_https = true

     [[services.ports]]
       handlers = ["tls", "http"]
       port = 443
   ```

4. **Deploy**:
   ```bash
   fly auth login
   fly launch
   fly postgres create --name your-db-name
   fly secrets set DATABASE_URL=<postgres-url>
   fly deploy
   ```

**Cost**: Free tier (3 VMs), then pay-as-you-go

---

### 4. **DigitalOcean App Platform**

**Why DigitalOcean?**
- ✅ Managed platform
- ✅ PostgreSQL included
- ✅ Auto-scaling
- ✅ Good documentation

**Deployment Steps:**

1. Go to https://cloud.digitalocean.com
2. Create App Platform project
3. Connect GitHub repo
4. Configure build/run commands
5. Add PostgreSQL database
6. Set environment variables
7. Deploy

**Cost**: $5/month minimum

---

## 🔧 Required Code Changes for Production

### 1. **Update Database Connection**

Create `database_config.py`:
```python
import os

def get_database_url():
    """Get database URL from environment or default to SQLite"""
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # PostgreSQL (production)
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return database_url
    else:
        # SQLite (local development)
        return 'sqlite:///admin_panel.db'
```

Update `admin_panel.py`:
```python
from database_config import get_database_url

app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
```

### 2. **Add Playwright to requirements.txt**

```txt
playwright==1.40.0
```

### 3. **Update Secret Key**

**IMPORTANT**: Change the hardcoded secret key!

```python
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-this-in-production')
```

### 4. **Add Production Settings**

```python
import os

# Production settings
if os.getenv('FLASK_ENV') == 'production':
    app.config['DEBUG'] = False
    app.config['TESTING'] = False
else:
    app.config['DEBUG'] = True
```

### 5. **Update Port Binding**

```python
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
```

---

## 📋 Pre-Deployment Checklist

- [ ] Add `playwright` to `requirements.txt`
- [ ] Update database connection to support PostgreSQL
- [ ] Change hardcoded `SECRET_KEY` to environment variable
- [ ] Update port binding to use `PORT` env variable
- [ ] Test Playwright installation locally
- [ ] Create `Procfile` (for Railway/Render)
- [ ] Set up environment variables
- [ ] Test database migration
- [ ] Update CORS settings if needed
- [ ] Test WebSocket connections

---

## 🎯 Quick Start: Railway (Recommended)

**Fastest way to deploy:**

1. **Push to GitHub**: `git push origin main`
2. **Go to Railway**: https://railway.app
3. **New Project** → **Deploy from GitHub**
4. **Select repo**: `aqstoria/Amazon-Scraper`
5. **Add PostgreSQL** database
6. **Set environment variables**:
   - `SECRET_KEY` (generate a random string)
   - `DATABASE_URL` (auto-set by Railway)
7. **Deploy!** 🚀

Railway will automatically:
- Detect Python project
- Install dependencies
- Install Playwright browsers
- Deploy your app
- Give you a public URL

---

## 🔗 GitHub Repository

Your project is connected to: **https://github.com/aqstoria/Amazon-Scraper**

Make sure your code is pushed to GitHub before deploying!

---

## 💡 Need Help?

- **Railway Docs**: https://docs.railway.app
- **Render Docs**: https://render.com/docs
- **Fly.io Docs**: https://fly.io/docs

