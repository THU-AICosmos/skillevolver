#!/usr/bin/env python3
"""Generate synthetic dirty grocery delivery data for the training variant."""

import numpy as np
import pandas as pd
import os
import random
import string

np.random.seed(2024)
random.seed(2024)

OUTPUT_DIR = "/app/data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 1. Generate Customer Demographics Survey (dirty)
# ============================================================
N_CUSTOMERS = 4200

customer_ids = [f"C_{random.randint(100000, 999999)}" for _ in range(N_CUSTOMERS)]
# Add ~50 duplicate IDs
dup_indices = np.random.choice(len(customer_ids), 50, replace=False)
for idx in dup_indices:
    customer_ids.append(customer_ids[idx])

n_total = len(customer_ids)

age_brackets = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
genders = ["Male", "Female", "Non-binary", "Prefer not to say"]
income_levels = ["Under $25k", "$25k-$50k", "$50k-$75k", "$75k-$100k", "$100k-$150k", "Over $150k"]
education_levels = ["High School", "Some College", "Associate", "Bachelor", "Master", "Doctorate"]
regions = ["Northeast", "Southeast", "Midwest", "Southwest", "West", "Pacific"]
diet_types = ["Omnivore", "Vegetarian", "Vegan", "Pescatarian", "Keto", "Gluten-Free"]
cooking_freq = ["Daily", "4-6 times/week", "2-3 times/week", "Once a week", "Rarely"]
exercise_freq = ["Never", "1-2 times/week", "3-4 times/week", "5+ times/week"]
pet_owner_vals = ["Yes", "No"]
has_kids_vals = ["Yes", "No"]
uses_coupons_vals = ["Yes", "No"]
owns_car_vals = ["Yes", "No"]
has_allergies_vals = ["Yes", "No"]
shops_organic_vals = ["Yes", "No"]

survey = pd.DataFrame({
    "CustomerID": customer_ids,
    "D-age-bracket": np.random.choice(age_brackets, n_total, p=[0.12, 0.25, 0.22, 0.18, 0.13, 0.10]),
    "D-gender": np.random.choice(genders, n_total, p=[0.45, 0.45, 0.05, 0.05]),
    "D-income-level": np.random.choice(income_levels, n_total, p=[0.10, 0.20, 0.25, 0.20, 0.15, 0.10]),
    "D-education": np.random.choice(education_levels, n_total, p=[0.15, 0.15, 0.10, 0.30, 0.20, 0.10]),
    "D-region": np.random.choice(regions, n_total, p=[0.20, 0.18, 0.17, 0.15, 0.15, 0.15]),
    "D-household-size": [str(x) if np.random.random() > 0.08 else f"{x} people" for x in np.random.choice([1,2,3,4,5,6,7,8,10,15], n_total, p=[0.15,0.25,0.20,0.18,0.10,0.05,0.03,0.02,0.01,0.01])],
    "D-diet-type": np.random.choice(diet_types, n_total, p=[0.50, 0.15, 0.08, 0.07, 0.12, 0.08]),
    "D-cooking-frequency": np.random.choice(cooking_freq, n_total, p=[0.20, 0.25, 0.30, 0.15, 0.10]),
    "D-exercise-frequency": np.random.choice(exercise_freq, n_total, p=[0.25, 0.30, 0.28, 0.17]),
    "D-pet-owner": np.random.choice(pet_owner_vals, n_total, p=[0.35, 0.65]),
    "D-has-children": np.random.choice(has_kids_vals, n_total, p=[0.40, 0.60]),
    "D-uses-coupons": np.random.choice(uses_coupons_vals, n_total, p=[0.55, 0.45]),
    "D-owns-car": np.random.choice(owns_car_vals, n_total, p=[0.70, 0.30]),
    "D-has-allergies": np.random.choice(has_allergies_vals, n_total, p=[0.20, 0.80]),
    "D-shops-organic": np.random.choice(shops_organic_vals, n_total, p=[0.30, 0.70]),
})

# Add missing values
for col in ["D-gender", "D-income-level", "D-diet-type", "D-cooking-frequency"]:
    mask = np.random.random(n_total) < 0.03
    survey.loc[mask, col] = np.nan

# Add some missing CustomerIDs
mask = np.random.random(n_total) < 0.005
survey.loc[mask, "CustomerID"] = np.nan

# Add missing values to D-has-allergies specifically for KNN imputation
mask = np.random.random(n_total) < 0.06
survey.loc[mask, "D-has-allergies"] = np.nan

survey.to_csv(f"{OUTPUT_DIR}/customer_survey_dirty.csv", index=False)
print(f"Generated customer_survey_dirty.csv: {len(survey)} rows")

# ============================================================
# 2. Generate Grocery Order Transactions (dirty)
# ============================================================

departments = [
    "Produce", "Dairy", "Bakery", "Meat & Poultry", "Seafood",
    "Deli & Prepared", "Frozen Foods", "Snacks & Chips", "Beverages",
    "Canned & Jarred", "Pasta & Grains", "Condiments & Sauces",
    "Breakfast & Cereal", "Baby Products", "Pet Supplies",
    "Health & Vitamins", "Personal Care", "Household Cleaning",
    "Paper & Wrap", "International Foods", "Organic & Natural",
    "Prepared Meals", "Wine & Spirits", "Floral & Garden",
    "Baking Supplies", "Spices & Seasonings", "Coffee & Tea",
    "Juice & Smoothies", "Candy & Chocolate", "Nuts & Dried Fruit",
    "Water & Seltzer", "Energy & Sports Drinks"
]

# Department base weights (popularity)
dept_weights = np.array([
    0.08, 0.07, 0.05, 0.06, 0.03,
    0.04, 0.05, 0.04, 0.06, 0.03,
    0.04, 0.03, 0.04, 0.02, 0.02,
    0.03, 0.03, 0.03, 0.02, 0.02,
    0.03, 0.03, 0.02, 0.01, 0.02,
    0.02, 0.03, 0.02, 0.02, 0.01,
    0.02, 0.01
])
dept_weights = dept_weights / dept_weights.sum()

# Date range: Jan 2020 to Nov 2020
dates = pd.date_range("2020-01-01", "2020-11-30", freq="D")

# Use valid (non-null, non-duplicate) customer IDs for transactions
valid_cids = [c for c in customer_ids if c is not None and isinstance(c, str)]
unique_cids = list(set(valid_cids))

# Generate transactions: ~250k orders
N_ORDERS = 280000

# Create seasonal patterns - surge some departments in November, slump others
# November treatment effect modifiers per department
nov_multipliers = {}
for i, dept in enumerate(departments):
    if dept in ["Bakery", "Wine & Spirits", "Candy & Chocolate", "Prepared Meals",
                "Snacks & Chips", "Baking Supplies", "Spices & Seasonings", "Coffee & Tea"]:
        nov_multipliers[dept] = np.random.uniform(1.8, 3.5)  # Surge departments
    elif dept in ["Pet Supplies", "Floral & Garden", "Baby Products", "Personal Care",
                  "Health & Vitamins", "Paper & Wrap", "Household Cleaning", "Energy & Sports Drinks"]:
        nov_multipliers[dept] = np.random.uniform(0.2, 0.5)  # Slump departments
    else:
        nov_multipliers[dept] = np.random.uniform(0.8, 1.2)  # Normal departments

records = []
for _ in range(N_ORDERS):
    # Pick date with slight trend toward later months
    date = np.random.choice(dates)
    month = pd.Timestamp(date).month

    # Adjust department weights based on month
    adjusted_weights = dept_weights.copy()
    if month == 11:
        for j, d in enumerate(departments):
            adjusted_weights[j] *= nov_multipliers[d]
        adjusted_weights = adjusted_weights / adjusted_weights.sum()

    dept_idx = np.random.choice(len(departments), p=adjusted_weights)
    dept = departments[dept_idx]

    cid = np.random.choice(unique_cids)

    # Price depends on department
    base_prices = {
        "Produce": (2, 15), "Dairy": (3, 12), "Bakery": (3, 18),
        "Meat & Poultry": (5, 30), "Seafood": (8, 35), "Deli & Prepared": (5, 20),
        "Frozen Foods": (3, 15), "Snacks & Chips": (2, 10), "Beverages": (2, 12),
        "Canned & Jarred": (1, 8), "Pasta & Grains": (1, 7), "Condiments & Sauces": (2, 10),
        "Breakfast & Cereal": (3, 12), "Baby Products": (5, 25), "Pet Supplies": (5, 30),
        "Health & Vitamins": (8, 40), "Personal Care": (3, 20), "Household Cleaning": (3, 15),
        "Paper & Wrap": (2, 12), "International Foods": (3, 15), "Organic & Natural": (4, 20),
        "Prepared Meals": (6, 25), "Wine & Spirits": (8, 50), "Floral & Garden": (5, 30),
        "Baking Supplies": (2, 12), "Spices & Seasonings": (2, 10), "Coffee & Tea": (5, 20),
        "Juice & Smoothies": (3, 12), "Candy & Chocolate": (2, 15), "Nuts & Dried Fruit": (4, 15),
        "Water & Seltzer": (2, 8), "Energy & Sports Drinks": (2, 10)
    }

    lo, hi = base_prices.get(dept, (2, 15))
    price = round(np.random.uniform(lo, hi), 2)
    qty = np.random.choice([1, 1, 1, 2, 2, 3, 4, 5])

    # Price modification in November for surge categories
    if month == 11 and dept in ["Bakery", "Wine & Spirits", "Candy & Chocolate",
                                 "Prepared Meals", "Baking Supplies"]:
        price *= np.random.uniform(1.1, 1.3)
        price = round(price, 2)

    records.append({
        "CustomerID": cid,
        "Order Date": str(pd.Timestamp(date).date()),
        "Unit Price": price,
        "Quantity": qty,
        "Department": dept,
        "Delivery Region": np.random.choice(regions, p=[0.20, 0.18, 0.17, 0.15, 0.15, 0.15]),
    })

orders = pd.DataFrame(records)

# Add dirtiness: ~7% missing Department
mask = np.random.random(len(orders)) < 0.07
orders.loc[mask, "Department"] = np.nan

# ~3% missing CustomerID
mask = np.random.random(len(orders)) < 0.03
orders.loc[mask, "CustomerID"] = np.nan

# ~2% missing Unit Price
mask = np.random.random(len(orders)) < 0.02
orders.loc[mask, "Unit Price"] = np.nan

# ~1% missing Quantity
mask = np.random.random(len(orders)) < 0.01
orders.loc[mask, "Quantity"] = np.nan

# Add some duplicate rows
n_dup = int(len(orders) * 0.02)
dup_idx = np.random.choice(len(orders), n_dup, replace=True)
orders = pd.concat([orders, orders.iloc[dup_idx]], ignore_index=True)

# Shuffle
orders = orders.sample(frac=1, random_state=42).reset_index(drop=True)

orders.to_csv(f"{OUTPUT_DIR}/grocery_orders_2020_dirty.csv", index=False)
print(f"Generated grocery_orders_2020_dirty.csv: {len(orders)} rows")
print("All data files generated successfully!")
