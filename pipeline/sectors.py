"""SIC -> sector mapping, ordered most-specific first.

SIC is a 1930s taxonomy and the SEC's assignment is self-reported, so the edges
are imperfect: a company that has pivoted often keeps its original code. The
mapping is kept explicit and printable so any name can be traced back to the
rule that classified it.
"""
RULES = [
    # (low, high, sector)   inclusive range on the 4-digit SIC code
    (2833, 2836, "Healthcare"),        # pharma, biologics
    (3826, 3826, "Healthcare"),        # lab analytical: Agilent, Waters, Illumina, Mettler
    (3827, 3827, "Technology"),        # KLA + Coherent are 81% of this code by value
    (3829, 3829, "Healthcare"),        # Thermo Fisher dominates; ROK/ONTO/TRMB overridden below
    (3841, 3851, "Healthcare"),        # medical devices, ophthalmic
    (8000, 8099, "Healthcare"),        # health services
    (8731, 8734, "Healthcare"),        # commercial research labs
    (7320, 7329, "Financials"),        # credit rating & reporting agencies

    (3570, 3579, "Technology"),        # computer hardware
    (3661, 3669, "Technology"),        # communications equipment
    (3670, 3679, "Technology"),        # semiconductors, components
    (3812, 3812, "Technology"),        # search/navigation systems
    (7370, 7379, "Technology"),        # software, data processing
    (7389, 7389, "Technology"),        # business services n.e.c.

    (6500, 6599, "Real Estate"),
    (6798, 6798, "Real Estate"),       # REITs
    (6000, 6199, "Financials"),        # depository & credit institutions
    (6200, 6299, "Financials"),        # brokers, exchanges
    (6300, 6499, "Financials"),        # insurance
    (6700, 6797, "Financials"),        # holding & investment offices
    (6799, 6799, "Financials"),

    (1300, 1389, "Energy"),            # oil & gas extraction and services
    (2911, 2911, "Energy"),            # petroleum refining
    (4922, 4925, "Energy"),            # natural gas transmission
    (5171, 5172, "Energy"),            # petroleum wholesale
    (4900, 4991, "Utilities"),         # electric, gas, water, sanitary

    (4800, 4899, "Communication Svcs"),# telecom, broadcasting
    (2700, 2799, "Communication Svcs"),# publishing
    (7310, 7319, "Communication Svcs"),# advertising
    (7812, 7841, "Communication Svcs"),# motion pictures

    (1000, 1099, "Materials"),         # metal mining
    (1400, 1499, "Materials"),         # nonmetallic minerals
    (2600, 2699, "Materials"),         # paper
    (2800, 2824, "Materials"),         # industrial chemicals
    (2840, 2899, "Materials"),         # specialty chemicals
    (3080, 3089, "Materials"),         # plastics products
    (3200, 3299, "Materials"),         # stone, clay, glass
    (3300, 3399, "Materials"),         # primary metals

    (2000, 2199, "Consumer Staples"),  # food, beverages, tobacco
    (2840, 2844, "Consumer Staples"),  # soap, cosmetics
    (5400, 5499, "Consumer Staples"),  # food stores
    (5122, 5122, "Consumer Staples"),

    (2300, 2399, "Consumer Disc"),     # apparel
    (2500, 2599, "Consumer Disc"),     # furniture
    (3630, 3639, "Consumer Disc"),     # household appliances
    (3710, 3716, "Consumer Disc"),     # motor vehicles
    (3940, 3949, "Consumer Disc"),     # toys, sporting goods
    (5200, 5399, "Consumer Disc"),     # retail
    (5500, 5736, "Consumer Disc"),     # auto dealers through retail stores
    (5800, 5899, "Consumer Disc"),     # eating & drinking places
    (5900, 5999, "Consumer Disc"),
    (7000, 7099, "Consumer Disc"),     # hotels
    (7900, 7999, "Consumer Disc"),     # amusement & recreation

    (1500, 1799, "Industrials"),       # construction
    (3400, 3499, "Industrials"),       # fabricated metal
    (3500, 3558, "Industrials"),       # industrial machinery
    (3559, 3559, "Technology"),        # semiconductor equipment: Lam, Axcelis, Veeco
    (3560, 3569, "Industrials"),
    (3580, 3599, "Industrials"),
    (3600, 3629, "Industrials"),       # electrical equipment
    (3700, 3799, "Industrials"),       # transportation equipment (ex autos)
    (3800, 3811, "Industrials"),
    (3813, 3824, "Industrials"),
    (3825, 3825, "Technology"),        # semiconductor test: Teradyne, Cohu, Aehr
    (3860, 3899, "Industrials"),
    (4000, 4799, "Industrials"),       # transportation & logistics
    (5000, 5121, "Industrials"),       # durable goods wholesale
    (5130, 5169, "Industrials"),
    (8711, 8721, "Industrials"),       # engineering, accounting
    (7200, 7299, "Industrials"),       # personal services
    (7330, 7369, "Industrials"),       # staffing, business services
    (7500, 7699, "Industrials"),       # auto & misc repair
    (8200, 8399, "Industrials"),       # educational & social services

    # Gaps found by auditing which names fell through to "Unclassified".
    (3011, 3011, "Consumer Disc"),     # tyres
    (3021, 3021, "Consumer Disc"),     # rubber footwear -- Nike, Deckers
    (3060, 3079, "Industrials"),       # fabricated rubber -- Carlisle
    (3100, 3199, "Consumer Disc"),     # leather goods -- Tapestry
    (2451, 2452, "Consumer Disc"),     # mobile / prefabricated homes
    (2400, 2450, "Materials"),         # lumber & wood
    (2453, 2499, "Materials"),
    (3640, 3649, "Industrials"),       # electric lighting -- Acuity
    (3690, 3699, "Industrials"),       # misc electrical equipment
    (3990, 3999, "Industrials"),       # misc manufacturing
    (8700, 8710, "Industrials"),       # management services -- Paychex
    (8722, 8748, "Industrials"),       # consulting -- Gartner
    (1220, 1220, "Materials"),         # silver ores
    (1221, 1299, "Energy"),            # coal
    (100,  999,  "Consumer Staples"),  # agriculture
]

def sector_for(sic):
    """Return a sector name for a SIC code, or 'Unclassified'."""
    try: s = int(sic)
    except (TypeError, ValueError): return "Unclassified"
    for lo, hi, name in RULES:
        if lo <= s <= hi: return name
    return "Unclassified"

SECTOR_ORDER = ["Technology","Healthcare","Financials","Industrials","Consumer Disc",
                "Consumer Staples","Energy","Utilities","Materials","Real Estate",
                "Communication Svcs","Unclassified"]


# SIC is self-reported and often predates a company's current business. These are
# large names whose code lands them in the wrong sector under the range rules
# above; each is overridden explicitly so the exception is visible rather than
# buried in a range boundary.
OVERRIDE = {
    "ROK":  "Industrials",   # SIC 3829 -- factory automation, not life sciences
    "ONTO": "Technology",    # SIC 3829 -- semiconductor metrology
    "TRMB": "Technology",    # SIC 3829 -- positioning / GNSS
    "ENTG": "Technology",    # SIC 3089 -- semiconductor materials, not plastics
    "VLTO": "Industrials",   # SIC 3825 -- water quality instrumentation
    "ERII": "Industrials",   # SIC 3559 -- energy recovery devices
    "AZTA": "Healthcare",    # SIC 3559 -- life-science sample management
    "VELO": "Industrials",   # SIC 3559 -- metal 3D printing

    # SIC 7389 "Services-Computer Programming, Data Processing" is a catch-all
    # holding 72 names worth $1.99tn. Visa and Mastercard alone are 60% of it,
    # and GICS reclassified the payment networks to Financials in 2023.
    "V":    "Financials",    # payment network
    "MA":   "Financials",    # payment network
    "PYPL": "Financials",    # payments
    "GPN":  "Financials",    # merchant acquiring
    "FISV": "Financials",    # payments infrastructure
    "CPAY": "Financials",    # corporate payments
    "MSCI": "Financials",    # index & analytics
    "UBER": "Industrials",   # ground transportation
    "DASH": "Consumer Disc", # delivery marketplace
    "MELI": "Consumer Disc", # e-commerce
    "EBAY": "Consumer Disc", # e-commerce
}

def sector_for_ticker(sic, ticker):
    """Sector with explicit large-cap overrides applied on top of the SIC ranges."""
    return OVERRIDE.get((ticker or "").upper()) or sector_for(sic)
