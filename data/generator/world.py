"""Static world definition: cities, fictional names, merchant catalog, reference code tables."""
from __future__ import annotations

# Real city centroids (public geography) with fictional street names generated elsewhere.
CITIES = {
    "Columbus":    dict(state="OH", zip3="432", tz="America/New_York",    lat=39.9612, lon=-82.9988, area="614"),
    "Westerville": dict(state="OH", zip3="430", tz="America/New_York",    lat=40.1262, lon=-82.9291, area="614"),
    "Cleveland":   dict(state="OH", zip3="441", tz="America/New_York",    lat=41.4993, lon=-81.6944, area="216"),
    "Pittsburgh":  dict(state="PA", zip3="152", tz="America/New_York",    lat=40.4406, lon=-79.9959, area="412"),
    "Boston":      dict(state="MA", zip3="021", tz="America/New_York",    lat=42.3601, lon=-71.0589, area="617"),
    "Brooklyn":    dict(state="NY", zip3="112", tz="America/New_York",    lat=40.6782, lon=-73.9442, area="718"),
    "Jersey City": dict(state="NJ", zip3="073", tz="America/New_York",    lat=40.7178, lon=-74.0431, area="201"),
    "Chicago":     dict(state="IL", zip3="606", tz="America/Chicago",     lat=41.8781, lon=-87.6298, area="312"),
    "Austin":      dict(state="TX", zip3="787", tz="America/Chicago",     lat=30.2672, lon=-97.7431, area="512"),
    "Denver":      dict(state="CO", zip3="802", tz="America/Denver",      lat=39.7392, lon=-104.9903, area="303"),
    "Los Angeles": dict(state="CA", zip3="900", tz="America/Los_Angeles", lat=34.0522, lon=-118.2437, area="213"),
    "Seattle":     dict(state="WA", zip3="981", tz="America/Los_Angeles", lat=47.6062, lon=-122.3321, area="206"),
}
BACKGROUND_CITY_WEIGHTS = {
    "Columbus": 14, "Westerville": 4, "Cleveland": 12, "Pittsburgh": 8, "Boston": 9, "Brooklyn": 9,
    "Jersey City": 4, "Chicago": 10, "Austin": 8, "Denver": 8, "Los Angeles": 9, "Seattle": 7,
}

STREETS = ["Alder Crest", "Bramblewood", "Carroll Bend", "Dovetail", "Elmsworth", "Fennimore", "Glenhaven",
           "Harrowgate", "Ivybridge", "Juniper Hollow", "Kestrel Run", "Larchmont Rise", "Maple Ridge",
           "Norwood Fen", "Oriel", "Pemberly", "Quarry Lake", "Rookwood", "Saffron Hill", "Thistledown",
           "Umberfield", "Vantage Point", "Willowmere", "Yarrow", "Zephyr Glen", "Copperleaf", "Brindle",
           "Marigold", "Stonebrook", "Wharfside"]
STREET_SUFFIX = ["St", "Ave", "Dr", "Ln", "Rd", "Ct", "Way", "Pl", "Blvd"]

FIRST_NAMES = ["Avery", "Bellamy", "Cassian", "Darcy", "Emrys", "Fallon", "Greer", "Hollis", "Imani", "Jules",
               "Kiran", "Linden", "Marlo", "Noor", "Oakley", "Perrin", "Quinn", "Rowan", "Sasha", "Teagan",
               "Umi", "Vesper", "Wren", "Xiomara", "Yael", "Zuri", "Arlo", "Briar", "Cyrus", "Delphine",
               "Ezra", "Freya", "Gideon", "Hana", "Idris", "Juniper", "Kai", "Lior", "Mira", "Nico",
               "Odessa", "Pax", "Remy", "Soren", "Tamsin", "Ulla", "Valen", "Willa", "Yusuf", "Zadie",
               "Anouk", "Bastian", "Cleo", "Dashiell", "Elio", "Farah", "Gemma", "Hugo", "Ines", "Jasper"]
LAST_NAMES = ["Ashdown", "Blackwood-Ruiz", "Castellane", "Drummond", "Eversole", "Farrowby", "Galloway-Chen",
              "Hartwell", "Ibarra-Lund", "Jessup", "Kowalczyk", "Larkin", "Montague", "Nakashima-Hale",
              "Okonjo", "Pemberton", "Quillon", "Ravensworth", "Sutcliffe", "Tamura-Bell", "Underhill",
              "Vasquez-Moore", "Whitlock", "Yardley", "Zeller", "Abernathy", "Brightwater", "Coldiron",
              "Delacroix-Park", "Emberly", "Fairchild", "Greenhalgh", "Holloway", "Iverson-Tate", "Janowski",
              "Kingsley", "Lockridge", "Marchetti", "Northcott", "Osei-Grant", "Penhallow", "Rasmussen-Oda",
              "Stirling", "Thorne", "Valdivia", "Wexford", "Achebe-Lowe", "Brennan-Sato", "Crowe", "Dunmore"]
EMPLOYERS = ["Brightline Staffing", "Cobalt Ridge Health", "Meridian Freight Co", "Helix Analytics",
             "Tern & Finch Legal", "Northgate Schools", "Silverpine Logistics", "Bluestem Insurance",
             "Carver Design Studio", "Juniper Civic Services", "Orrin Manufacturing", "Rivermark Clinic"]

ACQUIRERS = [
    ("ACQ-01", "Harborstone Merchant Services", "441201"),
    ("ACQ-02", "Pinecrest Payments", "441305"),
    ("ACQ-03", "Tapr Payment Facilitation", "441417"),
    ("ACQ-04", "Keystone Card Acquiring", "441522"),
    ("ACQ-05", "Atlantica Global Acquiring", "441690"),
    ("ACQ-06", "Summit Commerce Bank", "441733"),
    ("ACQ-07", "Nimbus Digital Acquiring", "441808"),
    ("ACQ-08", "Ironbridge Processing", "441914"),
]

MCC = {
    "4121": "Taxicabs and Limousines (incl. ride-hail)", "4511": "Airlines, Air Carriers",
    "4814": "Telecommunication Services", "4899": "Cable, Satellite, and Other Pay Television/Streaming",
    "4900": "Utilities", "5311": "Department Stores", "5399": "Miscellaneous General Merchandise",
    "5411": "Grocery Stores, Supermarkets", "5541": "Service Stations", "5542": "Automated Fuel Dispensers",
    "5651": "Family Clothing Stores", "5661": "Shoe Stores", "5712": "Furniture, Home Furnishings",
    "5719": "Miscellaneous Home Furnishing Specialty Stores", "5732": "Electronics Stores",
    "5812": "Eating Places, Restaurants", "5814": "Fast Food Restaurants", "5815": "Digital Goods – Media",
    "5816": "Digital Goods – Games", "5817": "Digital Goods – Applications (excl. games)",
    "5818": "Digital Goods – Large Digital Goods Merchant", "5912": "Drug Stores and Pharmacies",
    "5947": "Gift, Card, Novelty, and Souvenir Shops", "5968": "Direct Marketing – Continuity/Subscription",
    "5969": "Direct Marketing – Other Direct Marketers", "5999": "Miscellaneous and Specialty Retail Stores",
    "7011": "Lodging – Hotels, Motels, Resorts", "7922": "Theatrical Producers and Ticket Agencies",
    "7997": "Membership Clubs (Sports, Recreation, Athletic)", "4722": "Travel Agencies and Tour Operators",
}

# Background merchant catalog: (category, mcc, channel, scope, name stems)
# scope: 'city' = one per listed city; 'national' = ship-anywhere / online.
MERCHANT_CATALOG = [
    ("grocery", "5411", "in_store", "city", ["Greenbasket Market", "Hearthside Grocers", "Fieldstone Foods"]),
    ("restaurant", "5812", "in_store", "city", ["Copper Kettle Bistro", "Lantern Row Kitchen", "Saltbox Diner"]),
    ("fast_food", "5814", "in_store", "city", ["Brisk Burger", "Tacoloco Express"]),
    ("fuel", "5542", "in_store", "city", ["Pinegrove Fuel", "Northstar Gas"]),
    ("pharmacy", "5912", "in_store", "city", ["Wellspring Pharmacy"]),
    ("utilities", "4900", "recurring", "city", ["Metro Power & Light"]),
    ("gym", "7997", "recurring", "city", ["Peakform Fitness"]),
    ("ecom_general", "5999", "ecommerce", "national", ["Cartwheel Goods", "Nookery", "Bramble & Box", "Ferntree Supply", "Hatchmark"]),
    ("electronics", "5732", "ecommerce", "national", ["Circuitry Loft", "Pixelwave Electronics", "Voltcart Online"]),
    ("apparel", "5651", "ecommerce", "national", ["Loomhouse Apparel", "Threadline Co", "Northweave"]),
    ("shoes", "5661", "ecommerce", "national", ["Solewright", "Paceline Shoes"]),
    ("home", "5719", "ecommerce", "national", ["Hearth & Hollow", "Linenworks"]),
    ("digital_media", "5815", "ecommerce", "national", ["Inkwell Books Digital", "Tunewell Music"]),
    ("games", "5816", "ecommerce", "national", ["Sparkden Games", "Voidline Media", "Cinderbox Games"]),
    ("software", "5817", "ecommerce", "national", ["Quillsoft Apps", "Taskhaven"]),
    ("streaming", "4899", "recurring", "national", ["Streamnest", "Reelhaven+", "Sonora Audio"]),
    ("subscription_box", "5968", "recurring", "national", ["Crateful", "Sprout Meal Kits", "Pawcrate Club"]),
    ("telecom", "4814", "recurring", "national", ["Relaywave Mobile"]),
    ("rideshare", "4121", "in_store", "national", ["Ridehop"]),
    ("airline", "4511", "ecommerce", "national", ["Bluecrest Airways", "Meridia Air"]),
    ("hotel", "7011", "in_store", "national", ["Cedarline Inn", "Portwood Suites", "The Alder House"]),
    ("tickets", "7922", "ecommerce", "national", ["Stagepass Tickets"]),
    ("department", "5311", "in_store", "city", ["Foxglove & Finch"]),
    ("gift_cards", "5947", "ecommerce", "national", ["Giftlane Cards"]),
]

# --------------------------------------------------------------- reference tables
REF_AVS = [
    ("Y", "Street address and 5-digit ZIP match"), ("A", "Street address matches; ZIP does not"),
    ("Z", "5-digit ZIP matches; street address does not"), ("N", "Neither street address nor ZIP match"),
    ("U", "Address information unavailable (issuer did not respond / non-US)"), ("R", "Retry; system unavailable"),
    ("S", "AVS not supported by issuer"), ("G", "Global non-AVS participant"),
]
REF_CVV2_RESULT = [
    ("M", "CVV2 match"), ("N", "CVV2 no match"), ("P", "Not processed"),
    ("S", "CVV2 should be on card but merchant indicated not present"), ("U", "Unable to verify / issuer not certified"),
]
REF_CVV2_PRESENCE = [("0", "CVV2 not provided"), ("1", "CVV2 value present"), ("2", "CVV2 on card but illegible"),
                     ("9", "Cardholder states CVV2 not present on card")]
REF_ECI = [
    ("05", "Visa: fully authenticated (EMV 3DS / Visa Secure)"),
    ("06", "Visa: authentication attempted (issuer/Visa attempts response)"),
    ("07", "Visa: non-authenticated e-commerce"),
]
REF_3DS_STATUS = [("Y", "Authenticated"), ("A", "Attempts processing performed"), ("N", "Not authenticated"),
                  ("U", "Authentication could not be performed"), ("R", "Rejected"), ("C", "Challenge required"),
                  ("I", "Informational only")]
REF_POS_ENTRY = [
    ("01", "Manual key entry (also used for e-commerce PAN entry)"), ("05", "Integrated circuit (chip) read"),
    ("07", "Contactless chip"), ("10", "Credential on file"), ("90", "Magnetic stripe read (full track)"),
    ("91", "Contactless magnetic stripe"), ("95", "Chip card read with unreliable CVV (fallback)"),
]
REF_COF = [
    ("none", "Not a stored-credential transaction"), ("cit_initial", "Cardholder-initiated; credential stored"),
    ("cit_subsequent", "Cardholder-initiated using stored credential"),
    ("mit_recurring", "Merchant-initiated recurring (fixed interval)"),
    ("mit_unscheduled", "Merchant-initiated unscheduled credential-on-file"),
    ("mit_installment", "Merchant-initiated installment"),
]
REF_AUTH_RESPONSE = [("00", "Approved"), ("05", "Do not honor"), ("51", "Insufficient funds"),
                     ("59", "Suspected fraud"), ("N7", "CVV2 decline")]

BANK_HOLIDAYS_2026 = [  # Lanternfield Bank closed (fictional bank calendar mirroring the Federal Reserve schedule)
    ("2026-01-01", "New Year's Day"), ("2026-01-19", "Martin Luther King Jr. Day"),
    ("2026-02-16", "Washington's Birthday"), ("2026-05-25", "Memorial Day"),
    ("2026-06-19", "Juneteenth National Independence Day"), ("2026-09-07", "Labor Day"),
    ("2026-10-12", "Columbus Day"), ("2026-11-11", "Veterans Day"), ("2026-11-26", "Thanksgiving Day"),
    ("2026-12-25", "Christmas Day"), ("2027-01-01", "New Year's Day"), ("2027-01-18", "Martin Luther King Jr. Day"),
]

# Daily EUR->USD reference rates (fictional network rates) for the C07 window.
FX_EUR_USD = {
    "2026-08-10": "1.0998", "2026-08-11": "1.1020", "2026-08-12": "1.1011", "2026-08-13": "1.0987",
    "2026-09-30": "1.0661", "2026-10-01": "1.0645", "2026-10-02": "1.0652", "2026-10-08": "1.0679",
}

VISA_CONDITIONS = [
    ("10.1", "EMV Liability Shift Counterfeit Fraud", "Fraud", "allocation"),
    ("10.2", "EMV Liability Shift Non-Counterfeit Fraud", "Fraud", "allocation"),
    ("10.3", "Other Fraud – Card-Present Environment", "Fraud", "allocation"),
    ("10.4", "Other Fraud – Card-Absent Environment", "Fraud", "allocation"),
    ("10.5", "Visa Fraud Monitoring Program", "Fraud", "allocation"),
    ("11.1", "Card Recovery Bulletin", "Authorization", "allocation"),
    ("11.2", "Declined Authorization", "Authorization", "allocation"),
    ("11.3", "No Authorization / Late Presentment", "Authorization", "allocation"),
    ("12.2", "Incorrect Transaction Code", "Processing Errors", "collaboration"),
    ("12.3", "Incorrect Currency", "Processing Errors", "collaboration"),
    ("12.4", "Incorrect Account Number", "Processing Errors", "collaboration"),
    ("12.5", "Incorrect Amount", "Processing Errors", "collaboration"),
    ("12.6", "Duplicate Processing / Paid by Other Means", "Processing Errors", "collaboration"),
    ("12.7", "Invalid Data", "Processing Errors", "collaboration"),
    ("13.1", "Merchandise/Services Not Received", "Consumer Disputes", "collaboration"),
    ("13.2", "Cancelled Recurring Transaction", "Consumer Disputes", "collaboration"),
    ("13.3", "Not as Described or Defective Merchandise/Services", "Consumer Disputes", "collaboration"),
    ("13.4", "Counterfeit Merchandise", "Consumer Disputes", "collaboration"),
    ("13.5", "Misrepresentation", "Consumer Disputes", "collaboration"),
    ("13.6", "Credit Not Processed", "Consumer Disputes", "collaboration"),
    ("13.7", "Cancelled Merchandise/Services", "Consumer Disputes", "collaboration"),
    ("13.8", "Original Credit Transaction Not Accepted", "Consumer Disputes", "collaboration"),
    ("13.9", "Non-Receipt of Cash at an ATM", "Consumer Disputes", "collaboration"),
]
