"""
Multi-user labeled transaction dataset for supervised anomaly detection.

300 users x ~2,400 transactions each = ~720,000+ rows total.
Anomaly rate: ~8-10% (realistic for financial monitoring).

7 User Personas:
  college_student       -- low budget, food/entertainment heavy, late-night normal
  working_professional  -- medium-high income, commute, gym, 9-5 schedule
  family_household      -- groceries heavy, utilities, school, daytime window
  frequent_traveler     -- transportation heavy, any-hour transactions
  high_income_spender   -- luxury merchants, large amounts, flexible schedule
  retired_user          -- healthcare heavy, stable/low spending, early hours
  gig_worker            -- variable income, irregular patterns, all-day spending

15 Anomaly Types:
  1.  small_card_testing     -- micro charges $0.10-$5 rapid succession
  2.  merchant_novelty       -- never-before-seen category merchant
  3.  behavioral_shift       -- gradual multi-category spending increase
  4.  geographic_anomaly     -- city-stamped merchants user never visits
  5.  time_anomaly           -- unusual hour for this specific persona
  6.  subscription_hijack    -- new recurring charge user did not authorize
  7.  silent_fraud           -- normal-range amount, unfamiliar merchant
  8.  frequency_burst        -- many charges in one day (card compromise)
  9.  dormant_account_spike  -- surge after a quiet spending period
  10. category_switch        -- large spend in rarely-used category
  11. merchant_duplication   -- same merchant charged twice in minutes
  12. velocity_anomaly       -- multiple transactions within 1-hour window
  13. mixed_anomaly_chain    -- several anomaly signals in the same day
  14. income_anomaly         -- unexpected deposit from unknown source
  15. behavioral_contradiction -- purchase contradicting user persona

Reproducibility: seed = SEED + user_index * 1000.

Usage:
  cd backend/ml/
  python -m data.generate_dataset
"""
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

SEED       = 42
N_USERS    = 300
START_DATE = datetime(2023, 1, 1)
END_DATE   = datetime(2025, 6, 30)

# ── Persona definitions ────────────────────────────────────────────────────────

PERSONAS = [
    "college_student",
    "working_professional",
    "family_household",
    "frequent_traveler",
    "high_income_spender",
    "retired_user",
    "gig_worker",
]

PERSONA_WEIGHTS = [0.15, 0.25, 0.20, 0.10, 0.10, 0.10, 0.10]

# Hour-of-day probability weights per persona (index 0=midnight ... 23=11pm)
PERSONA_HOUR_WEIGHTS: dict[str, list[int]] = {
    "college_student":      [1,1,1,1,0,0,0,0,1,2,2,2,3,3,3,3,4,5,6,8,9,8,7,5],
    "working_professional": [0,0,0,0,0,0,1,4,5,3,3,4,6,6,4,3,3,5,6,7,5,3,1,0],
    "family_household":     [0,0,0,0,0,0,1,3,4,3,3,4,5,5,4,4,4,5,5,4,3,2,1,0],
    "frequent_traveler":    [2,2,1,1,1,1,2,3,4,3,3,4,5,5,4,4,4,5,5,5,4,3,2,2],
    "high_income_spender":  [0,0,0,0,0,0,0,1,2,3,3,4,5,5,4,4,4,5,6,7,6,4,2,1],
    "retired_user":         [0,0,0,0,0,2,4,6,7,6,5,4,4,4,3,3,3,3,2,2,1,0,0,0],
    "gig_worker":           [0,0,0,0,0,0,1,2,3,4,4,5,5,5,5,5,5,5,5,4,3,2,1,0],
}

# Hours that are anomalous for each persona
PERSONA_ANOMALOUS_HOURS: dict[str, list[int]] = {
    "college_student":      [5, 6, 7],
    "working_professional": [1, 2, 3, 4],
    "family_household":     [0, 1, 2, 3, 4],
    "frequent_traveler":    [2, 3],
    "high_income_spender":  [2, 3, 4],
    "retired_user":         [22, 23, 0, 1, 2, 3],
    "gig_worker":           [1, 2, 3],
}

# Spending scale ranges per persona
PERSONA_SPENDING_SCALE: dict[str, tuple[float, float]] = {
    "college_student":      (0.35, 0.60),
    "working_professional": (0.85, 1.50),
    "family_household":     (1.00, 1.80),
    "frequent_traveler":    (1.20, 2.00),
    "high_income_spender":  (1.60, 3.00),
    "retired_user":         (0.65, 1.10),
    "gig_worker":           (0.55, 1.30),
}

# Per-persona category frequency multipliers
PERSONA_CATEGORY_FREQ: dict[str, dict[str, float]] = {
    "college_student": {
        "Food & Dining": 1.6, "Groceries": 0.5, "Transportation": 0.7,
        "Entertainment": 1.8, "Shopping": 0.6, "Utilities": 0.4,
        "Healthcare": 0.3, "Rent & Housing": 0.5,
    },
    "working_professional": {
        "Food & Dining": 1.2, "Groceries": 0.9, "Transportation": 1.3,
        "Entertainment": 0.8, "Shopping": 1.0, "Utilities": 1.0,
        "Healthcare": 0.6, "Rent & Housing": 1.0,
    },
    "family_household": {
        "Food & Dining": 0.9, "Groceries": 1.8, "Transportation": 1.0,
        "Entertainment": 0.7, "Shopping": 1.1, "Utilities": 1.4,
        "Healthcare": 1.2, "Rent & Housing": 1.0,
    },
    "frequent_traveler": {
        "Food & Dining": 1.4, "Groceries": 0.5, "Transportation": 2.0,
        "Entertainment": 1.0, "Shopping": 1.2, "Utilities": 0.8,
        "Healthcare": 0.5, "Rent & Housing": 0.8,
    },
    "high_income_spender": {
        "Food & Dining": 1.1, "Groceries": 0.8, "Transportation": 0.9,
        "Entertainment": 1.3, "Shopping": 1.8, "Utilities": 1.0,
        "Healthcare": 0.9, "Rent & Housing": 1.0,
    },
    "retired_user": {
        "Food & Dining": 0.8, "Groceries": 1.3, "Transportation": 0.7,
        "Entertainment": 0.6, "Shopping": 0.8, "Utilities": 1.2,
        "Healthcare": 2.0, "Rent & Housing": 1.0,
    },
    "gig_worker": {
        "Food & Dining": 1.3, "Groceries": 0.8, "Transportation": 1.5,
        "Entertainment": 0.7, "Shopping": 0.9, "Utilities": 0.9,
        "Healthcare": 0.5, "Rent & Housing": 0.9,
    },
}

# ── Merchant pools ─────────────────────────────────────────────────────────────

MERCHANT_POOLS: dict[str, list[str]] = {
    "Food & Dining": [
        "Starbucks", "McDonald's", "Chipotle", "Subway", "Pizza Hut",
        "Local Diner", "Panera Bread", "Tim Hortons", "Shake Shack", "Wendy's",
        "Chick-fil-A", "Taco Bell", "Domino's", "KFC", "Burger King",
        "Dunkin'", "Five Guys", "Panda Express", "Olive Garden", "Applebee's",
        "IHOP", "Denny's", "Arby's", "Popeyes", "Sonic Drive-In",
        "Jack in the Box", "Whataburger", "Corner Cafe", "The Grill", "Noodle Bar",
    ],
    "Groceries": [
        "Walmart", "Kroger", "Whole Foods", "ALDI", "Costco",
        "Trader Joe's", "Safeway", "Publix", "H-E-B", "Wegmans",
        "Food Lion", "Giant Eagle", "Meijer", "WinCo Foods", "Sam's Club",
        "ShopRite", "Stop & Shop", "Sprouts", "Fresh Market", "BJ's Wholesale",
    ],
    "Transportation": [
        "Shell Gas", "BP Gas", "ExxonMobil", "Uber", "Lyft",
        "MTA Transit", "Petro-Canada", "Chevron", "Speedway", "Sunoco",
        "Circle K", "7-Eleven Gas", "Valero", "Marathon Gas", "Citgo",
        "Amtrak", "Greyhound", "Yellow Cab", "Via Rideshare", "Zipcar",
    ],
    "Entertainment": [
        "Netflix", "Spotify", "AMC Theaters", "Steam",
        "Xbox Game Pass", "YouTube Premium", "Disney+", "Apple TV+",
        "Hulu", "HBO Max", "Regal Cinemas", "Ticketmaster", "StubHub",
        "PlayStation Store", "Nintendo eShop", "Twitch", "ESPN+", "Peacock",
        "Crunchyroll", "Paramount+",
    ],
    "Shopping": [
        "Amazon", "Target", "H&M", "Best Buy", "Zara", "Nike Store", "IKEA",
        "Macy's", "Nordstrom", "Gap", "Old Navy", "Forever 21", "Adidas",
        "HomeGoods", "TJ Maxx", "Marshalls", "Ross", "Burlington",
        "Kohl's", "JCPenney", "Wayfair", "Overstock", "Etsy", "eBay",
        "Apple Store", "Samsung Store", "GameStop", "Dick's Sporting Goods",
    ],
    "Utilities": [
        "Electric Company", "Water Authority", "Comcast Internet",
        "Verizon Mobile", "Bell Canada", "AT&T", "T-Mobile",
        "Spectrum", "Cox Communications", "CenturyLink",
        "Duke Energy", "Pacific Gas & Electric", "Con Edison",
        "National Grid", "American Water", "NRG Energy",
    ],
    "Healthcare": [
        "CVS Pharmacy", "Walgreens", "CityMD Urgent Care", "Dr. Patel Medical",
        "Rite Aid", "OptumRx", "LabCorp", "Quest Diagnostics",
        "Kaiser Permanente", "MinuteClinic", "Dental Associates",
        "Vision Center", "GoHealth Urgent Care", "MedExpress",
    ],
    "Rent & Housing": [
        "City Properties LLC", "Landlord AutoPay",
        "Greystar Properties", "Equity Residential", "AvalonBay",
        "Lincoln Property Co", "Camden Property", "National Realty",
        "Harbor View Apts", "Maple Street Rentals",
    ],
}

SUSPICIOUS_MERCHANTS: list[tuple] = [
    ("Casino Royale",          "Entertainment",  200.0,  3000.0),
    ("Online Poker Network",   "Entertainment",  100.0,  2000.0),
    ("Crypto Exchange Pro",    "Shopping",       500.0,  6000.0),
    ("Wire Transfer Overseas", "Shopping",      1000.0,  8000.0),
    ("Foreign ATM Withdrawal", "Shopping",       300.0,  2500.0),
    ("Luxury Watch Boutique",  "Shopping",      2000.0, 15000.0),
    ("Pawn Shop Cash",         "Shopping",        50.0,   800.0),
    ("Offshore Betting",       "Entertainment",  200.0,  5000.0),
    ("Dark Web Marketplace",   "Shopping",       100.0,  3000.0),
    ("Unlicensed Dealer",      "Shopping",       300.0,  4000.0),
]

GEO_ANOMALY_MERCHANTS: list[tuple] = [
    ("Miami Beach Hotel & Spa",  "Entertainment",  300.0,  1200.0),
    ("Las Vegas Casino Resort",  "Entertainment",  500.0,  3000.0),
    ("NYC Fifth Ave Boutique",   "Shopping",       800.0,  5000.0),
    ("Tokyo Electronics Hub",    "Shopping",       200.0,  2000.0),
    ("Paris Duty Free",          "Shopping",       150.0,  1500.0),
    ("London Pub & Restaurant",  "Food & Dining",   40.0,   300.0),
    ("Dubai Luxury Mall",        "Shopping",       500.0,  8000.0),
    ("Denver Ski Resort",        "Entertainment",  200.0,  2000.0),
    ("New Orleans Jazz Club",    "Entertainment",  100.0,   800.0),
    ("Vegas Strip ATM Fee",      "Shopping",       300.0,  2000.0),
    ("Seattle Airport Lounge",   "Entertainment",   50.0,   400.0),
    ("Austin Music Festival",    "Entertainment",  100.0,  1000.0),
    ("Chicago Deep Dish & Bar",  "Food & Dining",   25.0,   200.0),
    ("Miami Nightclub VIP",      "Entertainment",  200.0,  1500.0),
    ("LA Dispensary Shop",       "Healthcare",      50.0,   400.0),
]

SUBSCRIPTION_HIJACK_MERCHANTS: list[tuple] = [
    ("UnknownStreamingPro",  "Entertainment",  15.99, 29.99),
    ("CloudStorage Plus",    "Shopping",        9.99, 19.99),
    ("PremiumNewsDaily",     "Entertainment",   7.99, 14.99),
    ("VPNSecureAnonymous",   "Shopping",       11.99, 19.99),
    ("OnlineGamingUnlocked", "Entertainment",  12.99, 24.99),
    ("FitnessAppPremium",    "Healthcare",      8.99, 15.99),
    ("AntiVirusPro2024",     "Shopping",        4.99, 12.99),
    ("DatingPlatformGold",   "Entertainment",  29.99, 59.99),
    ("EbookLibraryMonthly",  "Entertainment",   9.99, 19.99),
    ("CloudBackupService",   "Shopping",       14.99, 29.99),
]

PERSONA_CONTRADICTION_MERCHANTS: dict[str, list[tuple]] = {
    "college_student": [
        ("Luxury Watch Boutique", "Shopping",       2000.0,  8000.0),
        ("Fine Dining Reserve",   "Food & Dining",   200.0,   600.0),
        ("Private Jet Charter",   "Transportation", 5000.0, 15000.0),
    ],
    "working_professional": [
        ("Offshore Betting",   "Entertainment", 500.0, 3000.0),
        ("Pawn Shop Cash",     "Shopping",       50.0,  500.0),
        ("Cash Advance ATM",   "Shopping",      200.0, 1000.0),
    ],
    "family_household": [
        ("Casino Night Club",    "Entertainment", 300.0, 2000.0),
        ("Crypto Exchange Pro",  "Shopping",     1000.0, 5000.0),
        ("Offshore Betting",     "Entertainment", 200.0, 1500.0),
    ],
    "frequent_traveler": [
        ("Pawn Shop Express", "Shopping",  50.0,  400.0),
        ("Unlicensed Dealer", "Shopping", 300.0, 2000.0),
        ("Dark Web VPN Shop", "Shopping", 200.0, 1000.0),
    ],
    "high_income_spender": [
        ("Payday Loan Express",  "Shopping", 200.0, 1000.0),
        ("Check Cashing Center", "Shopping", 100.0,  500.0),
        ("Pawn Shop Cash",       "Shopping",  50.0,  300.0),
    ],
    "retired_user": [
        ("Gaming PC Ultra",  "Shopping",       1500.0, 4000.0),
        ("Youth Sports Store","Shopping",        300.0, 1200.0),
        ("Club Entry & Bar", "Entertainment",   100.0,  600.0),
    ],
    "gig_worker": [
        ("Luxury Watch Boutique", "Shopping",    2000.0, 10000.0),
        ("Fine Dining Reserve",   "Food & Dining", 300.0,   800.0),
        ("Private Car Service",   "Transportation",500.0,  2000.0),
    ],
}

# Legitimate recurring subscriptions a user might have
SUBSCRIPTION_SERVICES: list[dict] = [
    {"merchant": "Netflix",           "category": "Entertainment", "amount": 15.99},
    {"merchant": "Spotify",           "category": "Entertainment", "amount": 9.99},
    {"merchant": "YouTube Premium",   "category": "Entertainment", "amount": 13.99},
    {"merchant": "Disney+",           "category": "Entertainment", "amount": 10.99},
    {"merchant": "Hulu",              "category": "Entertainment", "amount": 17.99},
    {"merchant": "HBO Max",           "category": "Entertainment", "amount": 15.99},
    {"merchant": "Apple TV+",         "category": "Entertainment", "amount": 9.99},
    {"merchant": "Xbox Game Pass",    "category": "Entertainment", "amount": 14.99},
    {"merchant": "Crunchyroll",       "category": "Entertainment", "amount": 7.99},
    {"merchant": "Amazon Prime",      "category": "Shopping",      "amount": 14.99},
    {"merchant": "Verizon Mobile",    "category": "Utilities",     "amount": 75.00},
    {"merchant": "Comcast Internet",  "category": "Utilities",     "amount": 89.99},
    {"merchant": "Spectrum",          "category": "Utilities",     "amount": 79.99},
    {"merchant": "CVS Pharmacy",      "category": "Healthcare",    "amount": 35.00},
    {"merchant": "Gym Membership",    "category": "Healthcare",    "amount": 40.00},
    {"merchant": "iCloud Storage",    "category": "Shopping",      "amount": 2.99},
]

BASE_CATEGORIES: dict = {
    "Food & Dining":  {"amount_mean": 18.0,   "amount_std": 7.0,  "amount_min": 4.0,    "amount_max": 55.0,   "anomaly_min": 300.0,  "anomaly_max": 900.0,   "freq_per_month": 25, "n_merchants": 6},
    "Groceries":      {"amount_mean": 85.0,   "amount_std": 28.0, "amount_min": 20.0,   "amount_max": 200.0,  "anomaly_min": 600.0,  "anomaly_max": 1400.0,  "freq_per_month": 8,  "n_merchants": 4},
    "Transportation": {"amount_mean": 42.0,   "amount_std": 18.0, "amount_min": 5.0,    "amount_max": 140.0,  "anomaly_min": 500.0,  "anomaly_max": 1800.0,  "freq_per_month": 12, "n_merchants": 5},
    "Entertainment":  {"amount_mean": 22.0,   "amount_std": 10.0, "amount_min": 5.0,    "amount_max": 80.0,   "anomaly_min": 400.0,  "anomaly_max": 1200.0,  "freq_per_month": 5,  "n_merchants": 5},
    "Shopping":       {"amount_mean": 60.0,   "amount_std": 32.0, "amount_min": 10.0,   "amount_max": 280.0,  "anomaly_min": 1000.0, "anomaly_max": 5000.0,  "freq_per_month": 8,  "n_merchants": 6},
    "Utilities":      {"amount_mean": 105.0,  "amount_std": 22.0, "amount_min": 40.0,   "amount_max": 200.0,  "anomaly_min": 600.0,  "anomaly_max": 1500.0,  "freq_per_month": 4,  "n_merchants": 3},
    "Healthcare":     {"amount_mean": 48.0,   "amount_std": 28.0, "amount_min": 5.0,    "amount_max": 200.0,  "anomaly_min": 800.0,  "anomaly_max": 3000.0,  "freq_per_month": 2,  "n_merchants": 3},
    "Rent & Housing": {"amount_mean": 1100.0, "amount_std": 0.0,  "amount_min": 1100.0, "amount_max": 1100.0, "anomaly_min": 2200.0, "anomaly_max": 2500.0,  "freq_per_month": 1,  "n_merchants": 2},
}

# ── Low-level helpers ──────────────────────────────────────────────────────────

def _normal_amount(cfg: dict, rng: np.random.Generator) -> float:
    raw = rng.normal(cfg["amount_mean"], max(cfg["amount_std"], 0.01))
    return round(float(np.clip(raw, cfg["amount_min"], cfg["amount_max"])), 2)


def _anomaly_amount(cfg: dict, rng: np.random.Generator) -> float:
    return round(float(rng.uniform(cfg["anomaly_min"], cfg["anomaly_max"])), 2)


def _persona_hour(persona: str, rng: np.random.Generator) -> int:
    weights = PERSONA_HOUR_WEIGHTS[persona]
    total   = sum(weights)
    probs   = [w / total for w in weights]
    return int(rng.choice(24, p=probs))


def _make_row(counter: list, user_id: str, date: datetime, merchant: str,
              amount: float, category: str, txn_type: str,
              notes: str, is_anomaly: int) -> dict:
    counter[0] += 1
    return {
        "transaction_id":   f"TXN{counter[0]:06d}",
        "user_id":          user_id,
        "transaction_date": date.strftime("%Y-%m-%d %H:%M:%S"),
        "merchant":         merchant,
        "amount":           amount,
        "category":         category,
        "transaction_type": txn_type,
        "notes":            notes,
        "is_anomaly":       is_anomaly,
    }


def _season_amount_multiplier(date: datetime, category: str) -> float:
    """Seasonal spend patterns: holiday shopping surge, summer entertainment bump."""
    month = date.month
    if category == "Shopping" and month in (11, 12):
        return 1.40
    if category == "Entertainment" and month in (6, 7, 8):
        return 1.25
    if category == "Healthcare" and month == 1:
        return 1.20
    if category == "Food & Dining" and month in (6, 7, 8):
        return 1.15
    return 1.0


# ── User profile generation ────────────────────────────────────────────────────

def _generate_user_profile(user_idx: int, rng: np.random.Generator) -> dict:
    persona = str(rng.choice(PERSONAS, p=PERSONA_WEIGHTS))
    lo, hi  = PERSONA_SPENDING_SCALE[persona]
    spending_scale = float(rng.uniform(lo, hi))

    freq_mults = PERSONA_CATEGORY_FREQ[persona]
    categories: dict = {}

    for cat, base in BASE_CATEGORIES.items():
        persona_freq = freq_mults.get(cat, 1.0)
        cat_scale    = spending_scale * float(rng.uniform(0.85, 1.15))
        freq         = max(1, round(base["freq_per_month"] * persona_freq * float(rng.uniform(0.80, 1.20))))

        pool   = MERCHANT_POOLS[cat]
        n_pick = min(base["n_merchants"], len(pool))
        merchants = [str(m) for m in rng.choice(pool, size=n_pick, replace=False)]

        a_mean = round(base["amount_mean"] * cat_scale, 2)
        a_std  = round(base["amount_std"]  * cat_scale, 2)
        a_min  = round(base["amount_min"]  * cat_scale, 2)
        a_max  = round(base["amount_max"]  * cat_scale, 2)

        anom_scale = spending_scale * float(rng.uniform(0.9, 1.1))
        an_min = round(base["anomaly_min"] * anom_scale, 2)
        an_max = round(base["anomaly_max"] * anom_scale, 2)

        if cat == "Rent & Housing":
            rent_ranges = {
                "college_student":      (400.0,  900.0),
                "working_professional": (900.0, 2200.0),
                "family_household":     (1200.0, 3000.0),
                "frequent_traveler":    (1000.0, 2500.0),
                "high_income_spender":  (2000.0, 5000.0),
                "retired_user":         (600.0,  1500.0),
                "gig_worker":           (600.0,  1800.0),
            }
            rlo, rhi = rent_ranges[persona]
            rent      = round(float(rng.uniform(rlo, rhi)), 2)
            a_mean = a_min = a_max = rent
            a_std  = 0.0
            an_min = round(rent * 2.0, 2)
            an_max = round(rent * 2.5, 2)

        categories[cat] = {
            "merchants":      merchants,
            "amount_mean":    a_mean,
            "amount_std":     a_std,
            "amount_min":     a_min,
            "amount_max":     a_max,
            "anomaly_min":    an_min,
            "anomaly_max":    an_max,
            "freq_per_month": freq,
        }

    # Per-persona income structure
    if persona == "college_student":
        income_sources = [
            {"merchant": "Part-Time Job Payroll", "amount": round(spending_scale * 900.0, 2),
             "std": round(spending_scale * 100.0, 2), "frequency": "biweekly"},
            {"merchant": "Tutoring Payment",       "amount": round(spending_scale * 80.0, 2),
             "std": round(spending_scale * 40.0, 2), "frequency": "occasional"},
        ]
    elif persona == "working_professional":
        income_sources = [
            {"merchant": "Employer Direct Deposit", "amount": round(spending_scale * 2800.0, 2),
             "std": 0.0, "frequency": "biweekly"},
            {"merchant": "Consulting Bonus",         "amount": round(spending_scale * 600.0, 2),
             "std": round(spending_scale * 200.0, 2), "frequency": "occasional"},
        ]
    elif persona == "family_household":
        income_sources = [
            {"merchant": "Primary Payroll DD",   "amount": round(spending_scale * 2600.0, 2),
             "std": 0.0, "frequency": "biweekly"},
            {"merchant": "Secondary Payroll DD", "amount": round(spending_scale * 1800.0, 2),
             "std": 0.0, "frequency": "biweekly"},
        ]
    elif persona == "frequent_traveler":
        income_sources = [
            {"merchant": "Employer Direct Deposit", "amount": round(spending_scale * 3500.0, 2),
             "std": 0.0, "frequency": "biweekly"},
            {"merchant": "Expense Reimbursement",   "amount": round(spending_scale * 800.0, 2),
             "std": round(spending_scale * 300.0, 2), "frequency": "occasional"},
        ]
    elif persona == "high_income_spender":
        income_sources = [
            {"merchant": "Executive Payroll",    "amount": round(spending_scale * 6000.0, 2),
             "std": 0.0, "frequency": "biweekly"},
            {"merchant": "Investment Dividend",  "amount": round(spending_scale * 2000.0, 2),
             "std": round(spending_scale * 800.0, 2), "frequency": "occasional"},
        ]
    elif persona == "retired_user":
        income_sources = [
            {"merchant": "Pension Direct Deposit",   "amount": round(spending_scale * 2200.0, 2),
             "std": 0.0, "frequency": "monthly"},
            {"merchant": "Social Security Payment",  "amount": round(spending_scale * 1400.0, 2),
             "std": 0.0, "frequency": "monthly"},
        ]
    else:  # gig_worker
        income_sources = [
            {"merchant": "Uber Eats Payout",      "amount": round(spending_scale * 600.0, 2),
             "std": round(spending_scale * 250.0, 2), "frequency": "weekly"},
            {"merchant": "Freelance Client Wire", "amount": round(spending_scale * 1200.0, 2),
             "std": round(spending_scale * 500.0, 2), "frequency": "occasional"},
            {"merchant": "TaskRabbit Payout",     "amount": round(spending_scale * 300.0, 2),
             "std": round(spending_scale * 150.0, 2), "frequency": "occasional"},
        ]

    # 3-5 recurring subscription services
    n_subs = int(rng.integers(3, 6))
    sub_indices = rng.choice(len(SUBSCRIPTION_SERVICES), size=n_subs, replace=False).tolist()
    subscriptions = [SUBSCRIPTION_SERVICES[i] for i in sub_indices]

    return {
        "persona":       persona,
        "categories":    categories,
        "income_sources": income_sources,
        "subscriptions": subscriptions,
    }


# ── Normal row generators ──────────────────────────────────────────────────────

def _normal_expenses(user_id: str, profile: dict,
                     start: datetime, end: datetime,
                     ctr: list, rng: np.random.Generator) -> list:
    rows      = []
    months    = max(1, (end.year - start.year) * 12 + (end.month - start.month))
    days_span = max(1, (end - start).days)
    persona   = profile["persona"]

    for category, cfg in profile["categories"].items():
        n       = int(cfg["freq_per_month"] * months)
        offsets = sorted(rng.integers(0, days_span, size=n).tolist())
        for offset in offsets:
            date = start + timedelta(
                days=int(offset),
                hours=_persona_hour(persona, rng),
                minutes=int(rng.integers(0, 60)),
            )
            season_mult = _season_amount_multiplier(date, category)
            raw_amount  = _normal_amount(cfg, rng) * season_mult
            amount      = round(float(np.clip(raw_amount, cfg["amount_min"], cfg["amount_max"] * 1.5)), 2)
            rows.append(_make_row(
                ctr, user_id, date,
                str(rng.choice(cfg["merchants"])),
                amount, category, "expense", "", 0,
            ))
    return rows


def _recurring_subscriptions(user_id: str, profile: dict,
                              start: datetime, end: datetime,
                              ctr: list, rng: np.random.Generator) -> list:
    rows    = []
    persona = profile["persona"]

    for sub in profile["subscriptions"]:
        current = start.replace(day=int(rng.integers(1, 28)))
        while current <= end:
            jitter  = int(rng.integers(0, 2))
            pay_day = current + timedelta(days=jitter)
            if pay_day > end:
                break
            rows.append(_make_row(
                ctr, user_id,
                pay_day.replace(hour=_persona_hour(persona, rng), minute=int(rng.integers(0, 60))),
                sub["merchant"], sub["amount"],
                sub["category"], "expense", "subscription", 0,
            ))
            # advance one month
            next_month = current.month + 1 if current.month < 12 else 1
            next_year  = current.year if current.month < 12 else current.year + 1
            current    = current.replace(year=next_year, month=next_month)
    return rows


def _income_transactions(user_id: str, profile: dict,
                          start: datetime, end: datetime,
                          ctr: list, rng: np.random.Generator) -> list:
    rows      = []
    days_span = max(1, (end - start).days)
    months    = max(1, (end.year - start.year) * 12 + (end.month - start.month))

    for src in profile["income_sources"]:
        freq = src["frequency"]

        if freq == "biweekly":
            current = start
            while current <= end:
                jitter   = int(rng.integers(0, 3)) - 1
                pay_date = current + timedelta(days=jitter)
                if pay_date > end:
                    break
                amount = max(200.0, round(float(
                    rng.normal(src["amount"], max(src["std"], 0.01))
                ), 2))
                rows.append(_make_row(
                    ctr, user_id, pay_date.replace(hour=9, minute=0),
                    src["merchant"], amount, "Income", "income", "salary", 0,
                ))
                current += timedelta(days=14)

        elif freq == "weekly":
            current = start
            while current <= end:
                jitter   = int(rng.integers(0, 2))
                pay_date = current + timedelta(days=jitter)
                if pay_date > end:
                    break
                amount = max(50.0, round(float(
                    rng.normal(src["amount"], max(src["std"], 0.01))
                ), 2))
                rows.append(_make_row(
                    ctr, user_id, pay_date.replace(hour=10, minute=0),
                    src["merchant"], amount, "Income", "income", "gig", 0,
                ))
                current += timedelta(days=7)

        elif freq == "monthly":
            current = start
            while current <= end:
                pay_date = current.replace(day=1) + timedelta(days=int(rng.integers(0, 3)))
                if pay_date > end:
                    break
                amount = max(200.0, round(float(
                    rng.normal(src["amount"], max(src["std"], 0.01))
                ), 2))
                rows.append(_make_row(
                    ctr, user_id, pay_date.replace(hour=9, minute=0),
                    src["merchant"], amount, "Income", "income", "pension", 0,
                ))
                next_month = current.month + 1 if current.month < 12 else 1
                next_year  = current.year if current.month < 12 else current.year + 1
                current    = current.replace(year=next_year, month=next_month)

        else:  # occasional
            n = max(1, min(months // 2, days_span))
            for offset in rng.choice(days_span, size=n, replace=False):
                date   = start + timedelta(days=int(offset), hours=10)
                amount = max(50.0, round(float(
                    rng.normal(src["amount"], max(src["std"], 0.01))
                ), 2))
                rows.append(_make_row(
                    ctr, user_id, date,
                    src["merchant"], amount, "Income", "income", "freelance", 0,
                ))
    return rows


# ── 15 Anomaly generators ──────────────────────────────────────────────────────

def _anom_small_card_testing(user_id: str, profile: dict,
                              start: datetime, end: datetime,
                              ctr: list, rng: np.random.Generator) -> list:
    """4 fraud events: rapid micro-charges ($0.10-$5) to verify card is active."""
    rows         = []
    days_span    = max(1, (end - start).days)
    expense_cats = [c for c in profile["categories"] if c != "Rent & Housing" and c != "Income"]

    for _ in range(4):
        base_day  = start + timedelta(days=int(rng.integers(0, days_span)))
        category  = str(rng.choice(expense_cats))
        cfg       = profile["categories"][category]
        n_charges = int(rng.integers(4, 8))
        base_hour = int(rng.integers(0, 23))
        for k in range(n_charges):
            date = base_day.replace(
                hour=base_hour,
                minute=int(rng.integers(0, 60)),
                second=int(rng.integers(0, 60)),
            ) + timedelta(minutes=k * int(rng.integers(2, 8)))
            rows.append(_make_row(
                ctr, user_id, date,
                str(rng.choice(cfg["merchants"])),
                round(float(rng.uniform(0.10, 5.00)), 2),
                category, "expense", "card test micro-charge", 1,
            ))
    return rows


def _anom_merchant_novelty(user_id: str, profile: dict,
                            start: datetime, end: datetime,
                            ctr: list, rng: np.random.Generator) -> list:
    """10 transactions at merchants the user has never visited, with high amounts."""
    rows         = []
    days_span    = max(1, (end - start).days)
    expense_cats = [c for c in profile["categories"] if c != "Rent & Housing"]

    for offset in rng.choice(days_span, size=10, replace=False):
        date = start + timedelta(
            days=int(offset),
            hours=int(rng.integers(0, 24)),
            minutes=int(rng.integers(0, 60)),
        )
        category = str(rng.choice(expense_cats))
        cfg      = profile["categories"][category]
        pool     = MERCHANT_POOLS[category]
        known    = set(cfg["merchants"])
        novel    = [m for m in pool if m not in known]
        if not novel:
            novel = pool
        merchant = str(rng.choice(novel))
        rows.append(_make_row(
            ctr, user_id, date, merchant,
            _anomaly_amount(cfg, rng),
            category, "expense", "novel merchant high amount", 1,
        ))
    return rows


def _anom_behavioral_shift(user_id: str, profile: dict,
                            start: datetime, end: datetime,
                            ctr: list, rng: np.random.Generator) -> list:
    """3 events: gradual increase in spending across 3+ categories over 2 weeks."""
    rows         = []
    days_span    = max(30, (end - start).days)
    persona      = profile["persona"]
    expense_cats = [c for c in profile["categories"] if c != "Rent & Housing"]

    for _ in range(3):
        event_start = start + timedelta(days=int(rng.integers(0, days_span - 14)))
        n_cats = int(rng.integers(3, 5))
        chosen = list(rng.choice(expense_cats, size=min(n_cats, len(expense_cats)), replace=False))
        for day_offset in range(14):
            for category in chosen:
                if rng.random() < 0.4:
                    cfg    = profile["categories"][category]
                    date   = event_start + timedelta(
                        days=day_offset,
                        hours=_persona_hour(persona, rng),
                        minutes=int(rng.integers(0, 60)),
                    )
                    # Escalating amounts: 2x-5x normal
                    mult   = 2.0 + (day_offset / 14.0) * 3.0
                    amount = round(float(np.clip(cfg["amount_mean"] * mult,
                                                 cfg["amount_min"], cfg["anomaly_max"])), 2)
                    rows.append(_make_row(
                        ctr, user_id, date,
                        str(rng.choice(cfg["merchants"])),
                        amount, category, "expense", "behavioral shift escalation", 1,
                    ))
    return rows


def _anom_geographic_anomaly(user_id: str, profile: dict,
                              start: datetime, end: datetime,
                              ctr: list, rng: np.random.Generator) -> list:
    """12 transactions at city-stamped merchants far from user's home area."""
    rows      = []
    days_span = max(1, (end - start).days)

    for offset in rng.choice(days_span, size=12, replace=False):
        date = start + timedelta(
            days=int(offset),
            hours=int(rng.integers(0, 24)),
            minutes=int(rng.integers(0, 60)),
        )
        merchant_name, category, amin, amax = GEO_ANOMALY_MERCHANTS[
            int(rng.integers(0, len(GEO_ANOMALY_MERCHANTS)))
        ]
        rows.append(_make_row(
            ctr, user_id, date,
            merchant_name,
            round(float(rng.uniform(amin, amax)), 2),
            category, "expense", "geographic anomaly", 1,
        ))
    return rows


def _anom_time_anomaly(user_id: str, profile: dict,
                        start: datetime, end: datetime,
                        ctr: list, rng: np.random.Generator) -> list:
    """10 high-value transactions at hours anomalous for this specific persona."""
    rows         = []
    days_span    = max(1, (end - start).days)
    persona      = profile["persona"]
    anom_hours   = PERSONA_ANOMALOUS_HOURS[persona]
    expense_cats = [c for c in profile["categories"] if c != "Rent & Housing"]

    for offset in rng.choice(days_span, size=10, replace=False):
        date = (start + timedelta(days=int(offset))).replace(
            hour=int(rng.choice(anom_hours)),
            minute=int(rng.integers(0, 60)),
        )
        category = str(rng.choice(expense_cats))
        cfg      = profile["categories"][category]
        rows.append(_make_row(
            ctr, user_id, date,
            str(rng.choice(cfg["merchants"])),
            _anomaly_amount(cfg, rng),
            category, "expense", f"unusual hour for {persona}", 1,
        ))
    return rows


def _anom_subscription_hijack(user_id: str, profile: dict,
                               start: datetime, end: datetime,
                               ctr: list, rng: np.random.Generator) -> list:
    """1-2 unauthorized recurring subscriptions appearing monthly for 4-8 months."""
    rows    = []
    persona = profile["persona"]
    n_subs  = int(rng.integers(1, 3))

    for _ in range(n_subs):
        hijack_merchant, category, amin, amax = SUBSCRIPTION_HIJACK_MERCHANTS[
            int(rng.integers(0, len(SUBSCRIPTION_HIJACK_MERCHANTS)))
        ]
        days_span = max(1, (end - start).days)
        sub_start = start + timedelta(days=int(rng.integers(0, max(1, days_span - 240))))
        sub_day   = int(rng.integers(1, 28))
        months    = int(rng.integers(4, 9))
        current   = sub_start.replace(day=sub_day)

        for _ in range(months):
            if current > end:
                break
            rows.append(_make_row(
                ctr, user_id,
                current.replace(hour=_persona_hour(persona, rng), minute=int(rng.integers(0, 60))),
                hijack_merchant,
                round(float(rng.uniform(amin, amax)), 2),
                category, "expense", "subscription hijack", 1,
            ))
            next_month = current.month + 1 if current.month < 12 else 1
            next_year  = current.year if current.month < 12 else current.year + 1
            current    = current.replace(year=next_year, month=next_month)
    return rows


def _anom_silent_fraud(user_id: str, profile: dict,
                        start: datetime, end: datetime,
                        ctr: list, rng: np.random.Generator) -> list:
    """15 charges: normal-range amounts at unfamiliar merchants (hard-to-detect)."""
    rows         = []
    days_span    = max(1, (end - start).days)
    persona      = profile["persona"]
    expense_cats = [c for c in profile["categories"] if c != "Rent & Housing"]

    for offset in rng.choice(days_span, size=15, replace=False):
        date = start + timedelta(
            days=int(offset),
            hours=_persona_hour(persona, rng),
            minutes=int(rng.integers(0, 60)),
        )
        category = str(rng.choice(expense_cats))
        cfg      = profile["categories"][category]
        pool     = MERCHANT_POOLS[category]
        known    = set(cfg["merchants"])
        novel    = [m for m in pool if m not in known]
        if not novel:
            novel = pool
        # Amount in normal range (1.8x-3x normal — elevated but not obvious)
        amount = round(float(np.clip(
            cfg["amount_mean"] * float(rng.uniform(1.8, 3.0)),
            cfg["amount_min"], cfg["anomaly_min"] * 0.6,
        )), 2)
        rows.append(_make_row(
            ctr, user_id, date, str(rng.choice(novel)),
            amount, category, "expense", "silent fraud blended", 1,
        ))
    return rows


def _anom_frequency_burst(user_id: str, profile: dict,
                           start: datetime, end: datetime,
                           ctr: list, rng: np.random.Generator) -> list:
    """7 card-compromise bursts: 1 normal + 5-8 rapid charges on same day."""
    rows         = []
    days_span    = max(1, (end - start).days)
    expense_cats = [c for c in profile["categories"] if c != "Rent & Housing"]
    burst_cats   = sorted(
        expense_cats,
        key=lambda c: profile["categories"][c]["freq_per_month"],
        reverse=True,
    )[:4]

    for _ in range(7):
        burst_day = start + timedelta(days=int(rng.integers(0, days_span)))
        category  = str(rng.choice(burst_cats))
        cfg       = profile["categories"][category]

        # One normal transaction to anchor the day
        rows.append(_make_row(
            ctr, user_id, burst_day.replace(hour=9, minute=0),
            str(rng.choice(cfg["merchants"])),
            _normal_amount(cfg, rng), category, "expense", "", 0,
        ))
        for _ in range(int(rng.integers(5, 9))):
            date = burst_day.replace(
                hour=int(rng.integers(9, 24)),
                minute=int(rng.integers(0, 60)),
            )
            rows.append(_make_row(
                ctr, user_id, date,
                str(rng.choice(cfg["merchants"])),
                _normal_amount(cfg, rng),
                category, "expense", "frequency burst", 1,
            ))
    return rows


def _anom_dormant_spike(user_id: str, profile: dict,
                         start: datetime, end: datetime,
                         ctr: list, rng: np.random.Generator) -> list:
    """Surge of 10-14 transactions after a quiet 3-4 week gap."""
    rows         = []
    days_span    = max(60, (end - start).days)
    persona      = profile["persona"]
    expense_cats = [c for c in profile["categories"] if c != "Rent & Housing"]

    # Pick 2 such events
    for _ in range(2):
        spike_day  = start + timedelta(days=int(rng.integers(30, days_span - 7)))
        n_charges  = int(rng.integers(10, 15))
        for k in range(n_charges):
            date = spike_day + timedelta(
                days=int(rng.integers(0, 4)),
                hours=_persona_hour(persona, rng),
                minutes=int(rng.integers(0, 60)),
            )
            category = str(rng.choice(expense_cats))
            cfg      = profile["categories"][category]
            rows.append(_make_row(
                ctr, user_id, date,
                str(rng.choice(cfg["merchants"])),
                _anomaly_amount(cfg, rng),
                category, "expense", "dormant account spike", 1,
            ))
    return rows


def _anom_category_switch(user_id: str, profile: dict,
                           start: datetime, end: datetime,
                           ctr: list, rng: np.random.Generator) -> list:
    """8 large purchases in categories this user almost never uses."""
    rows         = []
    days_span    = max(1, (end - start).days)
    persona      = profile["persona"]
    freq_mults   = PERSONA_CATEGORY_FREQ[persona]
    rare_cats    = sorted(
        [c for c in profile["categories"] if c != "Rent & Housing"],
        key=lambda c: freq_mults.get(c, 1.0),
    )[:3]

    for offset in rng.choice(days_span, size=8, replace=False):
        date = start + timedelta(
            days=int(offset),
            hours=int(rng.integers(8, 22)),
            minutes=int(rng.integers(0, 60)),
        )
        category = str(rng.choice(rare_cats))
        cfg      = profile["categories"][category]
        rows.append(_make_row(
            ctr, user_id, date,
            str(rng.choice(cfg["merchants"])),
            _anomaly_amount(cfg, rng),
            category, "expense", "category switch anomaly", 1,
        ))
    return rows


def _anom_merchant_duplication(user_id: str, profile: dict,
                                start: datetime, end: datetime,
                                ctr: list, rng: np.random.Generator) -> list:
    """3 duplicate-billing events: same merchant charged twice within 5 minutes."""
    rows         = []
    days_span    = max(1, (end - start).days)
    expense_cats = [c for c in profile["categories"] if c != "Rent & Housing"]

    for _ in range(3):
        date = start + timedelta(
            days=int(rng.integers(0, days_span)),
            hours=int(rng.integers(8, 22)),
            minutes=int(rng.integers(0, 55)),
        )
        category = str(rng.choice(expense_cats))
        cfg      = profile["categories"][category]
        merchant = str(rng.choice(cfg["merchants"]))
        amount   = _normal_amount(cfg, rng)

        rows.append(_make_row(ctr, user_id, date, merchant, amount, category, "expense", "original charge", 0))
        duplicate_date = date + timedelta(minutes=int(rng.integers(1, 6)))
        rows.append(_make_row(ctr, user_id, duplicate_date, merchant, amount, category, "expense", "duplicate charge", 1))
    return rows


def _anom_velocity_anomaly(user_id: str, profile: dict,
                            start: datetime, end: datetime,
                            ctr: list, rng: np.random.Generator) -> list:
    """3 events: 4-7 different-category transactions within a 1-hour window."""
    rows         = []
    days_span    = max(1, (end - start).days)
    expense_cats = [c for c in profile["categories"] if c != "Rent & Housing"]

    for _ in range(3):
        base_time = start + timedelta(
            days=int(rng.integers(0, days_span)),
            hours=int(rng.integers(8, 22)),
        )
        n_charges = int(rng.integers(4, 8))
        for k in range(n_charges):
            date = base_time + timedelta(minutes=int(rng.integers(0, 55)))
            category = str(rng.choice(expense_cats))
            cfg      = profile["categories"][category]
            rows.append(_make_row(
                ctr, user_id, date,
                str(rng.choice(cfg["merchants"])),
                _anomaly_amount(cfg, rng),
                category, "expense", "velocity anomaly 1h burst", 1,
            ))
    return rows


def _anom_mixed_chain(user_id: str, profile: dict,
                       start: datetime, end: datetime,
                       ctr: list, rng: np.random.Generator) -> list:
    """2 events: a day with multiple anomaly signals — late hour + high amount + new merchant."""
    rows         = []
    days_span    = max(1, (end - start).days)
    persona      = profile["persona"]
    anom_hours   = PERSONA_ANOMALOUS_HOURS[persona]
    expense_cats = [c for c in profile["categories"] if c != "Rent & Housing"]

    for _ in range(2):
        base_day = start + timedelta(days=int(rng.integers(0, days_span)))
        n_txns   = int(rng.integers(6, 10))
        for _ in range(n_txns):
            date = base_day.replace(
                hour=int(rng.choice(anom_hours)),
                minute=int(rng.integers(0, 60)),
            )
            category = str(rng.choice(expense_cats))
            cfg      = profile["categories"][category]
            pool     = MERCHANT_POOLS[category]
            known    = set(cfg["merchants"])
            novel    = [m for m in pool if m not in known] or pool
            rows.append(_make_row(
                ctr, user_id, date, str(rng.choice(novel)),
                _anomaly_amount(cfg, rng),
                category, "expense", "mixed anomaly chain", 1,
            ))
    return rows


def _anom_income_anomaly(user_id: str, profile: dict,
                          start: datetime, end: datetime,
                          ctr: list, rng: np.random.Generator) -> list:
    """4 unexpected large income transactions from unknown sources."""
    rows      = []
    days_span = max(1, (end - start).days)
    spending_scale = float(profile["categories"]["Food & Dining"]["amount_mean"] / 18.0)
    unknown_sources = [
        "Unknown Wire Transfer",
        "Offshore Account Credit",
        "Unidentified Deposit",
        "Crypto Liquidation Deposit",
        "Foreign Payment Source",
    ]

    for offset in rng.choice(days_span, size=4, replace=False):
        date   = start + timedelta(days=int(offset), hours=int(rng.integers(8, 18)))
        amount = round(float(rng.uniform(3000.0, 15000.0)) * spending_scale, 2)
        source = str(rng.choice(unknown_sources))
        rows.append(_make_row(
            ctr, user_id, date, source, amount,
            "Income", "income", "income anomaly unknown source", 1,
        ))
    return rows


def _anom_behavioral_contradiction(user_id: str, profile: dict,
                                    start: datetime, end: datetime,
                                    ctr: list, rng: np.random.Generator) -> list:
    """6 purchases that directly contradict the user's persona profile."""
    rows      = []
    days_span = max(1, (end - start).days)
    persona   = profile["persona"]
    contradiction_pool = PERSONA_CONTRADICTION_MERCHANTS[persona]

    for offset in rng.choice(days_span, size=6, replace=False):
        date = start + timedelta(
            days=int(offset),
            hours=int(rng.integers(8, 22)),
            minutes=int(rng.integers(0, 60)),
        )
        merchant_name, category, amin, amax = contradiction_pool[
            int(rng.integers(0, len(contradiction_pool)))
        ]
        rows.append(_make_row(
            ctr, user_id, date, merchant_name,
            round(float(rng.uniform(amin, amax)), 2),
            category, "expense", f"behavioral contradiction for {persona}", 1,
        ))
    return rows


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_multiuser_dataset(
    n_users: int    = N_USERS,
    start: datetime = START_DATE,
    end: datetime   = END_DATE,
    seed: int       = SEED,
) -> pd.DataFrame:
    """
    Generate a fully labeled multi-user transaction DataFrame.

    Each user gets seed = seed + user_index * 1000 (deterministic, independent).
    Rows are sorted by user_id then transaction_date within each user block.
    """
    global_ctr: list  = [0]
    user_frames: list = []

    for i in range(n_users):
        user_id  = f"user_{i + 1:04d}"
        user_rng = np.random.default_rng(seed + i * 1000)
        profile  = _generate_user_profile(i, user_rng)

        rows = (
            _normal_expenses(user_id, profile, start, end, global_ctr, user_rng)
            + _recurring_subscriptions(user_id, profile, start, end, global_ctr, user_rng)
            + _income_transactions(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_small_card_testing(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_merchant_novelty(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_behavioral_shift(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_geographic_anomaly(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_time_anomaly(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_subscription_hijack(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_silent_fraud(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_frequency_burst(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_dormant_spike(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_category_switch(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_merchant_duplication(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_velocity_anomaly(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_mixed_chain(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_income_anomaly(user_id, profile, start, end, global_ctr, user_rng)
            + _anom_behavioral_contradiction(user_id, profile, start, end, global_ctr, user_rng)
        )

        df_user = pd.DataFrame(rows)
        df_user["transaction_date"] = pd.to_datetime(df_user["transaction_date"])
        user_frames.append(df_user.sort_values("transaction_date").reset_index(drop=True))

        if (i + 1) % 50 == 0:
            print(f"  Generated {i + 1}/{n_users} users ...")

    df = pd.concat(user_frames, ignore_index=True)
    df = df.sort_values(["user_id", "transaction_date"]).reset_index(drop=True)
    df["transaction_id"] = [f"TXN{i + 1:06d}" for i in range(len(df))]
    return df


def generate_dataset(
    user_id: str    = "user_0001",
    start: datetime = START_DATE,
    end: datetime   = END_DATE,
    seed: int       = SEED,
) -> pd.DataFrame:
    """Single-user generator kept for backward compatibility and inference testing."""
    try:
        user_idx = int(user_id.split("_")[1]) - 1
    except (IndexError, ValueError):
        user_idx = 0

    rng     = np.random.default_rng(seed + user_idx * 1000)
    ctr     = [0]
    profile = _generate_user_profile(user_idx, rng)

    rows = (
        _normal_expenses(user_id, profile, start, end, ctr, rng)
        + _recurring_subscriptions(user_id, profile, start, end, ctr, rng)
        + _income_transactions(user_id, profile, start, end, ctr, rng)
        + _anom_small_card_testing(user_id, profile, start, end, ctr, rng)
        + _anom_merchant_novelty(user_id, profile, start, end, ctr, rng)
        + _anom_behavioral_shift(user_id, profile, start, end, ctr, rng)
        + _anom_geographic_anomaly(user_id, profile, start, end, ctr, rng)
        + _anom_time_anomaly(user_id, profile, start, end, ctr, rng)
        + _anom_subscription_hijack(user_id, profile, start, end, ctr, rng)
        + _anom_silent_fraud(user_id, profile, start, end, ctr, rng)
        + _anom_frequency_burst(user_id, profile, start, end, ctr, rng)
        + _anom_dormant_spike(user_id, profile, start, end, ctr, rng)
        + _anom_category_switch(user_id, profile, start, end, ctr, rng)
        + _anom_merchant_duplication(user_id, profile, start, end, ctr, rng)
        + _anom_velocity_anomaly(user_id, profile, start, end, ctr, rng)
        + _anom_mixed_chain(user_id, profile, start, end, ctr, rng)
        + _anom_income_anomaly(user_id, profile, start, end, ctr, rng)
        + _anom_behavioral_contradiction(user_id, profile, start, end, ctr, rng)
    )

    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df = df.sort_values("transaction_date").reset_index(drop=True)
    df["transaction_id"] = [f"TXN{i + 1:05d}" for i in range(len(df))]
    return df


def main() -> None:
    out_path = os.path.join(os.path.dirname(__file__), "transactions_multiuser.csv")

    print(f"Generating multi-user dataset  ({N_USERS} users, {START_DATE.date()} to {END_DATE.date()}) ...")
    df = generate_multiuser_dataset()

    total   = len(df)
    n_anom  = int(df["is_anomaly"].sum())
    n_norm  = total - n_anom
    n_users = df["user_id"].nunique()

    print(f"\n  Total rows   : {total:,}")
    print(f"  Users        : {n_users}")
    print(f"  Avg per user : {total // n_users:,}")
    print(f"  Normal   (0) : {n_norm:,}  ({n_norm / total * 100:.1f}%)")
    print(f"  Anomaly  (1) : {n_anom:,}  ({n_anom / total * 100:.1f}%)")

    print("\n  Persona distribution:")
    # Persona stored in notes only; approximate from transaction counts
    print("  (7 personas: college_student, working_professional, family_household,")
    print("   frequent_traveler, high_income_spender, retired_user, gig_worker)")

    print("\n  Anomaly type breakdown (from notes field):")
    anom_df = df[df["is_anomaly"] == 1]
    for label in [
        "card test", "novel merchant", "behavioral shift", "geographic anomaly",
        "unusual hour", "subscription hijack", "silent fraud", "frequency burst",
        "dormant account", "category switch", "duplicate charge", "velocity anomaly",
        "mixed anomaly", "income anomaly", "behavioral contradiction",
    ]:
        count = int(anom_df["notes"].str.contains(label, case=False, na=False).sum())
        print(f"    {label:<35} : {count:>6}")

    print("\n  Per-user anomaly sample (first 10 users):")
    sample = (
        df.groupby("user_id")
        .agg(total=("is_anomaly", "count"), anomalies=("is_anomaly", "sum"))
        .assign(pct=lambda x: (x["anomalies"] / x["total"] * 100).round(1))
        .head(10)
    )
    print(sample.to_string())

    df.to_csv(out_path, index=False)
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"\n  Saved: {out_path}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
