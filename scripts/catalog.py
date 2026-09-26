"""Shared catalog and scenario constants for the Tremor Retail demo fixture.

Everything the generators produce comes from this file plus a fixed seed, so the
fixture is fully reproducible.
"""

from datetime import date

SEED = 26
STORE_NAME = "Gupta General Store, Indira Nagar"
START = date(2026, 6, 27)
DAYS = 90  # 27 Jun 2026 to 24 Sep 2026

SUPPLIERS = {
    "SHAKTI": {"name": "Shakti Wholesale", "addr": "Naka Hindola, Lucknow", "prefix": "SW", "gstin": "09ABCDE1234F1Z5"},
    "AWADH": {"name": "Awadh Grain Traders", "addr": "Aminabad, Lucknow", "prefix": "AGT", "gstin": "09FGHIJ5678K1Z2"},
    "METRO": {"name": "Metro FMCG Distributors", "addr": "Chinhat, Lucknow", "prefix": "MFD", "gstin": "09KLMNO9012P1Z8"},
}

# Invoice numbers and dates per supplier: (number, date). The last one is "current".
INVOICES = {
    "SHAKTI": [("SW-112", date(2026, 6, 29)), ("SW-151", date(2026, 8, 5)), ("SW-184", date(2026, 9, 10))],
    "AWADH": [("AGT-0714", date(2026, 7, 1)), ("AGT-0802", date(2026, 8, 8)), ("AGT-0911", date(2026, 9, 12))],
    "METRO": [("MFD-3301", date(2026, 6, 30)), ("MFD-3388", date(2026, 8, 6)), ("MFD-3452", date(2026, 9, 9))],
}
# Decoy D2: a one-off bulk basmati purchase on its own invoice.
BULK_INVOICE = ("AWADH", "AGT-0820B", date(2026, 8, 20))

# (product_id, shop name, invoice description, supplier, unit, size, base cost, selling price, daily units)
PRODUCTS = [
    ("SKU-OIL-1L", "Sunpure Cooking Oil 1 L", "SUNPURE OIL 1 LTR", "SHAKTI", "bottle", "1 L", 118, 135, 8),
    ("SKU-MUST-1L", "Fortune Mustard Oil 1 L", "FORTUNE KACHI GHANI 1L", "SHAKTI", "bottle", "1 L", 152, 170, 4),
    ("SKU-SUG-1K", "Sugar 1 kg", "SUGAR M30 1KG PKT", "SHAKTI", "packet", "1 kg", 42, 48, 10),
    ("SKU-TOOR-1K", "Toor Dal 1 kg", "TOOR DAL PREMIUM 1 KG", "SHAKTI", "packet", "1 kg", 128, 150, 5),
    ("SKU-MOONG-1K", "Moong Dal 1 kg", "MOONG DAL YELLOW 1KG", "SHAKTI", "packet", "1 kg", 112, 130, 3),
    ("SKU-SALT-1K", "Tata Salt 1 kg", "TATA SALT 1KG", "SHAKTI", "packet", "1 kg", 22, 28, 9),
    ("SKU-TEA-250", "Tata Tea Gold 250 g", "TATA TEA GOLD 250GM", "SHAKTI", "packet", "250 g", 138, 160, 4),
    ("SKU-GHEE-1L", "Amul Ghee 1 L", "AMUL GHEE TIN 1 LTR", "SHAKTI", "tin", "1 L", 560, 620, 1),
    ("SKU-POHA-500", "Poha 500 g", "POHA THICK 500 GM", "SHAKTI", "packet", "500 g", 28, 36, 3),
    ("SKU-BESAN-500", "Besan 500 g", "BESAN 500G", "SHAKTI", "packet", "500 g", 46, 56, 3),
    ("SKU-HALDI-100", "Turmeric Powder 100 g", "HALDI PWD 100GM", "SHAKTI", "packet", "100 g", 24, 32, 2),
    ("SKU-MIRCH-100", "Red Chilli Powder 100 g", "LAL MIRCH PWD 100GM", "SHAKTI", "packet", "100 g", 30, 40, 2),
    ("SKU-ATTA-5K", "Aashirvaad Atta 5 kg", "AASHIRVAAD ATTA 5KG BAG", "AWADH", "bag", "5 kg", 210, 260, 5),
    ("SKU-RICE-1K", "Sona Masoori Rice 1 kg", "SONA MASURI RICE 1 KG", "AWADH", "packet", "1 kg", 58, 70, 8),
    ("SKU-BAS-5K", "India Gate Basmati 5 kg", "INDIA GATE BASMATI 5KG", "AWADH", "bag", "5 kg", 520, 600, 1),
    ("SKU-MAIDA-1K", "Maida 1 kg", "MAIDA 1KG PKT", "AWADH", "packet", "1 kg", 34, 42, 3),
    ("SKU-SUJI-500", "Suji 500 g", "SOOJI RAVA 500G", "AWADH", "packet", "500 g", 24, 30, 2),
    ("SKU-CHANA-1K", "Kabuli Chana 1 kg", "KABULI CHANA 1KG", "AWADH", "packet", "1 kg", 118, 140, 2),
    ("SKU-RAJMA-1K", "Rajma 1 kg", "RAJMA CHITRA 1KG", "AWADH", "packet", "1 kg", 132, 155, 2),
    ("SKU-DALIA-500", "Dalia 500 g", "DALIA 500 GM", "AWADH", "packet", "500 g", 26, 34, 1),
    ("SKU-COKE-750", "Coca-Cola 750 ml", "COCA COLA PET 750ML", "METRO", "bottle", "750 ml", 34, 40, 6),
    ("SKU-FROOTI-600", "Frooti 600 ml", "FROOTI MANGO 600ML", "METRO", "bottle", "600 ml", 28, 35, 5),
    ("SKU-SPRITE-750", "Sprite 750 ml", "SPRITE PET 750ML", "METRO", "bottle", "750 ml", 34, 40, 4),
    ("SKU-WATER-1L", "Bisleri Water 1 L", "BISLERI 1LTR", "METRO", "bottle", "1 L", 15, 20, 12),
    ("SKU-PARLE-G", "Parle-G Biscuit 250 g", "PARLE G 250G", "METRO", "packet", "250 g", 20, 25, 10),
    ("SKU-MAGGI-280", "Maggi Noodles 280 g", "MAGGI 4 PACK 280G", "METRO", "packet", "280 g", 48, 56, 6),
    ("SKU-LAYS-52", "Lays Classic 52 g", "LAYS CLASSIC SALTED 52G", "METRO", "packet", "52 g", 17, 20, 7),
    ("SKU-BREAD-400", "Brown Bread 400 g", "BREAD BROWN 400G", "METRO", "packet", "400 g", 38, 45, 5),
    ("SKU-SURF-1K", "Surf Excel 1 kg", "SURF EXCEL EASY WASH 1KG", "METRO", "packet", "1 kg", 118, 140, 2),
    ("SKU-VIM-500", "Vim Bar 500 g", "VIM BAR 500G", "METRO", "packet", "500 g", 36, 45, 3),
    ("SKU-COLGATE-200", "Colgate Toothpaste 200 g", "COLGATE STRONG TEETH 200G", "METRO", "tube", "200 g", 96, 115, 2),
    ("SKU-LIFEBUOY-4", "Lifebuoy Soap 4 x 100 g", "LIFEBUOY 4X100G", "METRO", "pack", "400 g", 112, 135, 2),
    ("SKU-DETTOL-250", "Dettol Liquid 250 ml", "DETTOL ANTISEPTIC 250ML", "METRO", "bottle", "250 ml", 148, 175, 1),
    ("SKU-HARPIC-500", "Harpic 500 ml", "HARPIC POWER PLUS 500ML", "METRO", "bottle", "500 ml", 88, 105, 1),
]
BEVERAGES = {"SKU-COKE-750", "SKU-FROOTI-600", "SKU-SPRITE-750", "SKU-WATER-1L"}

# Planted cost paths per invoice index (0, 1, 2). Anything not listed gets small noise.
PLANTED_COSTS = {
    "SKU-OIL-1L": [118, 118, 132],  # S1 hero
    "SKU-ATTA-5K": [210, 222, 236],  # S2 flour, two rises
    "SKU-SUG-1K": [42, 42, 47],  # S4 sugar
    "SKU-TOOR-1K": [128, 128, 141],  # S5 toor dal
}
# Planted selling price changes: product -> list of (from_date, price)
PRICE_CHANGES = {
    "SKU-ATTA-5K": [(date(2026, 9, 18), 270)],  # S2: price catches up late
}
# Store calendar (also written to data/demo/calendar.json)
PROMOTIONS = [
    {"product_id": "SKU-OIL-1L", "start": date(2026, 7, 1), "end": date(2026, 7, 5), "price": 129, "label": "Monsoon oil offer"},
]
FESTIVAL = {
    "name": "Local mela week (store calendar)",
    "start": date(2026, 8, 7),
    "end": date(2026, 8, 16),
    "beverage_multiplier": 2.5,
}
# Planted stock shrink (count adjustments): product -> (date, units short)
SHRINK = {
    "SKU-OIL-1L": (date(2026, 9, 18), 12),  # part of hero evidence
    "SKU-RICE-1K": (date(2026, 9, 2), 20),  # S3 inventory discrepancy
}
