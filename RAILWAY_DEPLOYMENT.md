# 🚂 Railway Deployment Guide

## Quick Start

### Step 1: Create Railway Account
1. Go to https://railway.app
2. Sign up with your GitHub account
3. Click "New Project"

### Step 2: Deploy from GitHub
1. Select "Deploy from GitHub repo"
2. Authorize Railway to access your GitHub
3. Select repository: **Ahmadkhanworkspace/scrapper**
4. Railway will automatically detect Python and start building

### Step 3: Add PostgreSQL Database
1. In your Railway project dashboard, click **"+ New"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway will automatically:
   - Create a PostgreSQL database
   - Set `DATABASE_URL` environment variable
   - Provide connection details

### Step 4: Set Environment Variables
1. Go to your service settings
2. Click **"Variables"** tab
3. Add these environment variables:

```
SECRET_KEY=your-random-secret-key-here-change-this
FLASK_ENV=production
PORT=5000
```

**To generate a secure SECRET_KEY:**
```python
import secrets
print(secrets.token_hex(32))
```

### Step 5: Deploy
Railway will automatically:
- ✅ Install Python dependencies from `requirements.txt`
- ✅ Install Playwright browsers (Chromium)
- ✅ Run database initialization
- ✅ Start your Flask app

### Step 6: Get Your URL
1. Railway will provide a public URL like: `https://your-app.railway.app`
2. Click on the service → **"Settings"** → **"Generate Domain"** for a custom domain

---

## 🔧 Configuration Files

### `Procfile`
```
web: python admin_panel.py
```

### `nixpacks.toml`
Railway uses Nixpacks to build your app. The `nixpacks.toml` file configures:
- Python 3.11
- Node.js 18 (for Playwright)
- Playwright browser installation
- Build commands

### `requirements.txt`
All Python dependencies including:
- Flask and Flask extensions
- Playwright for browser automation
- PostgreSQL driver (psycopg2-binary)
- Scrapy and other scraping libraries

---

## 📊 Database Setup

The app automatically:
1. Detects `DATABASE_URL` environment variable
2. Initializes PostgreSQL tables on first run
3. Creates default admin user:
   - **Username**: `admin`
   - **Password**: `admin123`

**⚠️ Change the admin password after first login!**

---

## 🎯 Access Your App

Once deployed:
1. Visit your Railway URL: `https://your-app.railway.app`
2. Login with:
   - Username: `admin`
   - Password: `admin123`
3. Start scraping! 🚀

---

## 🔍 Monitoring & Logs

### View Logs
1. In Railway dashboard, click on your service
2. Go to **"Deployments"** tab
3. Click on a deployment to see logs
4. Or use **"Logs"** tab for real-time logs

### Common Issues

**Issue: Playwright browsers not installed**
- Solution: Railway automatically installs them via `nixpacks.toml`
- Check build logs to confirm installation

**Issue: Database connection failed**
- Solution: Make sure PostgreSQL service is added and `DATABASE_URL` is set
- Check that `init_postgres.py` ran successfully

**Issue: Port binding error**
- Solution: Railway sets `PORT` automatically, make sure your code uses `os.getenv('PORT', 5000)`

**Issue: App crashes on startup**
- Check logs for error messages
- Verify all environment variables are set
- Ensure `requirements.txt` has all dependencies

---

## 💰 Pricing

**Free Tier:**
- $5 credit per month
- Perfect for testing and small projects

**Hobby Plan:**
- $5/month per service
- Always-on services
- No sleep timeout

**Pro Plan:**
- $20/month
- More resources
- Better performance

---

## 🔄 Continuous Deployment

Railway automatically deploys when you:
- Push to `main` branch
- Merge pull requests
- Manually trigger deployment

To disable auto-deploy:
1. Go to service settings
2. **"Source"** tab
3. Toggle **"Auto Deploy"** off

---

## 🛠️ Custom Domain

1. Go to service **"Settings"**
2. Click **"Generate Domain"**
3. Railway provides: `your-app.railway.app`
4. Or add your own domain in **"Custom Domain"** section

---

## 📝 Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ Yes | - | PostgreSQL connection string (auto-set by Railway) |
| `SECRET_KEY` | ✅ Yes | - | Flask secret key for sessions |
| `FLASK_ENV` | No | `development` | Set to `production` for production |
| `PORT` | No | `5000` | Port to run on (auto-set by Railway) |

---

## 🚀 Next Steps

After deployment:
1. ✅ Change admin password
2. ✅ Configure scraper settings
3. ✅ Test scraping functionality
4. ✅ Set up monitoring
5. ✅ Configure custom domain (optional)

---

## 📞 Support

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **GitHub Issues**: https://github.com/Ahmadkhanworkspace/scrapper/issues

---

## ✅ Deployment Checklist

- [ ] Railway account created
- [ ] GitHub repository connected
- [ ] PostgreSQL database added
- [ ] Environment variables set
- [ ] App deployed successfully
- [ ] Can access admin panel
- [ ] Can login with admin credentials
- [ ] Database tables created
- [ ] Scraper test run successful

---

**Happy Deploying! 🎉**

