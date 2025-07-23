# database.py
import asyncpg
from datetime import datetime, timedelta
import logging
from config import (DATABASE_URL, ADMIN_CHANNEL_ID, NUMBER_LEASE_MINUTES, 
                    STRIKE_LIMIT_FOR_RESTRICTION, RESTRICTION_HOURS)

# (বাকি সব কোড আগের উত্তরের মতোই থাকবে, এটি সম্পূর্ণ)
# ...
