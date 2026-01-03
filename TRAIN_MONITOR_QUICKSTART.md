# Train Monitor - Quick Start Guide

**Status:** ✅ All 6 phases complete - Ready for deployment

---

## What's Ready

The UK Train Monitor system is **fully implemented** and ready to deploy:

- ✅ **Phase 1:** Foundation (models, notifier, providers)
- ✅ **Phase 2:** Darwin API Integration
- ✅ **Phase 3:** State Management (9/9 tests passing)
- ✅ **Phase 4:** Station Manager (5/5 tests passing)
- ✅ **Phase 5:** Main Monitor Application
- ✅ **Phase 6:** Docker Integration

**Total:** 3000+ lines of code, 14/14 tests passing

---

## Quick Start (5 minutes)

### Step 1: Get Darwin API Key

Tomorrow, register for Darwin API access:

**Option A: Official Darwin API** (recommended, free)
1. Go to: https://opendata.nationalrail.co.uk/
2. Click "Register for an account"
3. Activate your account via email
4. Request an API key (usually approved within 24 hours)

**Option B: departureboard.io** (instant, free, but may be down)
- No registration needed
- Just set `DARWIN_USE_DEPARTUREBOARD_IO=true`
- Note: Currently experiencing downtime

### Step 2: Configure Environment

Edit your `.env` file and add:

```bash
# Enable train monitoring
TRAIN_MONITOR_ENABLED=true

# Safe testing mode (recommended first)
TRAIN_MONITOR_DRY_RUN=true

# Darwin API key (from Step 1)
DARWIN_API_KEY=your_api_key_here

# Monitor Ely station
TRAIN_MONITOR_STATIONS=ELY

# Ely configuration
TRAIN_MONITOR_ELY_ENABLED=true
TRAIN_MONITOR_ELY_NAME=Ely
TRAIN_MONITOR_ELY_MODE=departures
TRAIN_MONITOR_ELY_INTERVAL=5
TRAIN_MONITOR_ELY_TIME_WINDOW=120
TRAIN_MONITOR_ELY_MAX_SERVICES=50
TRAIN_MONITOR_ELY_CHAT_ID=-1001234567890  # Your Telegram group ID
TRAIN_MONITOR_ELY_NOTIFICATIONS=true
TRAIN_MONITOR_ELY_MIN_DELAY=5
TRAIN_MONITOR_ELY_NOTIFY_CANCELLATIONS=true
TRAIN_MONITOR_ELY_NOTIFY_PLATFORM_CHANGES=true
```

**Tip:** See `.env.example` for complete configuration reference

### Step 3: Test in DRY-RUN Mode

```bash
# Start train monitor
docker compose up train-monitor

# You should see:
# 🚂 UK TRAIN MONITOR - STATION MANAGER 🚂
# 🔧 DRY-RUN MODE ACTIVE
# ✅ Station Manager created successfully
# Started monitoring for Ely (ELY) - check interval: 5 minutes
```

Watch the logs for simulated notifications:
```
[DRY-RUN] Would send to -1001234567890:
🚨 TRAIN DELAY - Ely
Cambridge → London Kings Cross
⏱️ DELAYED by 10 minutes
```

Press `Ctrl+C` to stop.

### Step 4: Go Live

Once testing looks good:

1. **Update `.env`:**
```bash
TRAIN_MONITOR_DRY_RUN=false  # Send real notifications
```

2. **Restart:**
```bash
docker compose restart train-monitor
```

3. **Monitor logs:**
```bash
docker compose logs -f train-monitor
```

4. **Check Telegram** for notifications when delays occur

---

## Common Commands

```bash
# Start (foreground, see logs)
docker compose up train-monitor

# Start (background)
docker compose up -d train-monitor

# View logs
docker compose logs -f train-monitor

# Stop
docker compose stop train-monitor

# Restart (after config changes)
docker compose restart train-monitor

# Check status
docker compose ps train-monitor

# Check health
docker inspect ukraine-bot-train-monitor --format='{{.State.Health.Status}}'
```

---

## Adding More Stations

Edit `.env` and add station configurations:

```bash
# Add Cambridge to the list
TRAIN_MONITOR_STATIONS=ELY,CBG

# Cambridge configuration
TRAIN_MONITOR_CBG_ENABLED=true
TRAIN_MONITOR_CBG_NAME=Cambridge
TRAIN_MONITOR_CBG_MODE=departures
TRAIN_MONITOR_CBG_INTERVAL=10
TRAIN_MONITOR_CBG_TIME_WINDOW=120
TRAIN_MONITOR_CBG_MAX_SERVICES=50
TRAIN_MONITOR_CBG_CHAT_ID=-1001234567890
TRAIN_MONITOR_CBG_NOTIFICATIONS=true
TRAIN_MONITOR_CBG_MIN_DELAY=10
TRAIN_MONITOR_CBG_NOTIFY_CANCELLATIONS=true
TRAIN_MONITOR_CBG_NOTIFY_PLATFORM_CHANGES=true
TRAIN_MONITOR_CBG_DESTINATIONS=KGX  # Only Kings Cross trains
```

Then restart:
```bash
docker compose restart train-monitor
```

---

## Troubleshooting

### Service won't start

**Check if enabled:**
```bash
grep TRAIN_MONITOR_ENABLED .env
# Should be: TRAIN_MONITOR_ENABLED=true
```

**View startup logs:**
```bash
docker compose logs train-monitor
```

### No notifications

**Still in DRY-RUN mode?**
```bash
grep TRAIN_MONITOR_DRY_RUN .env
# For production: TRAIN_MONITOR_DRY_RUN=false
```

**Check Telegram chat ID:**
```bash
grep CHAT_ID .env | grep ELY
# Should match your Telegram group
```

### API errors

**Try departureboard.io:**
```bash
# In .env:
DARWIN_USE_DEPARTUREBOARD_IO=true
```

---

## Documentation

**Complete guides in `specs/work_log/`:**
- [Phase 1: Foundation](specs/work_log/train_monitor_development_progress.md)
- [Phase 2: Darwin API](specs/work_log/train_monitor_phase2_complete_update.md)
- [Phase 3: State Management](specs/work_log/train_monitor_phase3_complete.md)
- [Phase 4: Station Manager](specs/work_log/train_monitor_phase4_complete.md)
- [Phase 5: Main Monitor](specs/work_log/train_monitor_phase5_complete.md)
- [Phase 6: Docker Integration](specs/work_log/train_monitor_phase6_complete.md)

**Architecture overview:**
- [Integration Plan](specs/work_log/train_monitor_integration_plan.md)

---

## Station CRS Codes (Quick Reference)

**Major stations:**
- ELY = Ely
- CBG = Cambridge
- KGX = London Kings Cross
- LST = London Liverpool Street
- NRW = Norwich
- IPW = Ipswich

**Full list:** https://www.nationalrail.co.uk/stations_destinations/48541.aspx

---

## What Happens Next

### Tomorrow (when you get API key):

1. ✅ Register for Darwin API at https://opendata.nationalrail.co.uk/
2. ✅ Add API key to `.env`
3. ✅ Start train monitor in DRY-RUN mode
4. ✅ Verify it detects real train data
5. ✅ Switch to production mode (`DRY_RUN=false`)
6. ✅ Enjoy automated train monitoring!

### System will automatically:

- 🚂 Check Ely station every 5 minutes
- 🔍 Detect delays, cancellations, platform changes
- 📱 Send notifications to your Telegram group
- ♻️ Auto-restart if it crashes
- 🏥 Report health status

---

## Support

If something doesn't work:

1. Check logs: `docker compose logs -f train-monitor`
2. Review troubleshooting in [Phase 6 docs](specs/work_log/train_monitor_phase6_complete.md)
3. Verify `.env` configuration against `.env.example`

---

**Status:** ✅ Ready for deployment
**Next action:** Get Darwin API key tomorrow and test!
**Last updated:** 2025-12-28
