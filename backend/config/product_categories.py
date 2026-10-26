# The Vault Campus Marketplace
# Created by James Williams - 10/26/26

"""
config/product_categories.py

Purpose:
The list of product categories (12 main categories, each with subcategories).
The migration copies this list into the product_categories table.

Notes:
- These are not the storefront style tags (storefronts.categories).
- A listing always uses a subcategory, or "Other".
- Never change a slug after release. To rename, change only the name.
- Order here is the order shown on the site.
- icon: picture used on the All Categories page (main categories only).
- description: optional help text in the seller's category picker.
- keywords: optional extra search words for the picker (e.g. "mac").
"""

OTHER_SLUG = "other"

PRODUCT_CATEGORIES = [
    {
        "slug": "clothing-and-apparel",
        "name": "Clothing & Apparel",
        "icon": "shirt",
        "children": [
            {"slug": "t-shirts-and-tops", "name": "T-Shirts & Tops", "keywords": ["tee", "t shirt", "tank", "blouse", "crop top", "polo"]},
            {"slug": "hoodies-and-sweatshirts", "name": "Hoodies & Sweatshirts", "keywords": ["hoodie", "crewneck", "sweater", "pullover", "zip up"]},
            {"slug": "jackets-and-coats", "name": "Jackets & Coats", "keywords": ["jacket", "coat", "puffer", "windbreaker", "blazer", "vest"]},
            {"slug": "jeans-and-pants", "name": "Jeans & Pants", "keywords": ["jeans", "denim", "trousers", "sweatpants", "joggers", "cargo"]},
            {"slug": "shorts", "name": "Shorts"},
            {"slug": "dresses-and-skirts", "name": "Dresses & Skirts", "keywords": ["dress", "skirt", "gown"]},
            {"slug": "activewear", "name": "Activewear", "keywords": ["gym clothes", "leggings", "sports bra", "athletic", "workout"]},
            {"slug": "formalwear", "name": "Formalwear", "keywords": ["suit", "tuxedo", "blazer", "formal", "gown", "prom"]},
            {"slug": "swimwear", "name": "Swimwear", "keywords": ["swimsuit", "bikini", "trunks"]},
            {"slug": "loungewear-and-sleepwear", "name": "Loungewear & Sleepwear", "keywords": ["pajamas", "pjs", "robe", "lounge"]},
            {"slug": "vintage-clothing", "name": "Vintage Clothing", "keywords": ["thrift", "retro", "y2k"]},
            {"slug": "other-clothing", "name": "Other Clothing"},
        ],
    },
    {
        "slug": "shoes-and-footwear",
        "name": "Shoes & Footwear",
        "icon": "shoe",
        "children": [
            {"slug": "sneakers", "name": "Sneakers", "keywords": ["jordans", "nike", "dunks", "air force", "kicks", "trainers", "yeezy"]},
            {"slug": "boots", "name": "Boots", "keywords": ["timberlands", "timbs", "chelsea", "uggs"]},
            {"slug": "sandals-and-slides", "name": "Sandals & Slides", "keywords": ["slides", "flip flops", "crocs"]},
            {"slug": "heels-and-flats", "name": "Heels & Flats", "keywords": ["heels", "pumps", "flats", "loafers"]},
            {"slug": "dress-shoes", "name": "Dress Shoes", "keywords": ["oxfords", "loafers", "formal shoes"]},
            {"slug": "athletic-shoes-and-cleats", "name": "Athletic Shoes & Cleats", "keywords": ["cleats", "running shoes", "basketball shoes"]},
            {"slug": "other-footwear", "name": "Other Footwear"},
        ],
    },
    {
        "slug": "electronics-and-technology",
        "name": "Electronics & Technology",
        "icon": "laptop",
        "children": [
            {"slug": "laptops-and-computers", "name": "Laptops & Computers", "keywords": ["mac", "macbook", "chromebook", "pc", "desktop", "imac", "gaming pc"]},
            {"slug": "phones", "name": "Phones", "keywords": ["iphone", "android", "samsung", "galaxy", "pixel", "cell phone", "smartphone"]},
            {"slug": "tablets-and-ereaders", "name": "Tablets & eReaders", "keywords": ["ipad", "kindle", "tablet", "e reader"]},
            {"slug": "headphones-and-speakers", "name": "Headphones & Speakers", "keywords": ["airpods", "earbuds", "beats", "headset", "bluetooth speaker", "jbl"]},
            {"slug": "computer-accessories", "name": "Computer Accessories", "keywords": ["keyboard", "mouse", "charger", "usb", "hard drive", "webcam"]},
            {"slug": "phone-accessories", "name": "Phone Accessories", "keywords": ["phone case", "charger", "cable", "popsocket", "screen protector"]},
            {"slug": "cameras-and-photography", "name": "Cameras & Photography", "keywords": ["camera", "lens", "gopro", "tripod", "film"]},
            {"slug": "monitors-and-displays", "name": "Monitors & Displays", "keywords": ["monitor", "screen", "display"]},
            {"slug": "smartwatches-and-wearables", "name": "Smartwatches & Wearables", "keywords": ["apple watch", "fitbit", "smartwatch"]},
            {"slug": "other-electronics", "name": "Other Electronics"},
        ],
    },
    {
        "slug": "home-and-dorm-essentials",
        "name": "Home & Dorm Essentials",
        "icon": "lamp",
        "children": [
            {"slug": "furniture", "name": "Furniture", "keywords": ["desk", "chair", "table", "couch", "futon", "shelf"]},
            {"slug": "bedding-and-pillows", "name": "Bedding & Pillows", "keywords": ["sheets", "comforter", "blanket", "pillow", "mattress topper"]},
            {"slug": "storage-and-organization", "name": "Storage & Organization", "keywords": ["bins", "drawers", "hangers", "shelves", "organizer"]},
            {"slug": "lamps-and-lighting", "name": "Lamps & Lighting", "keywords": ["lamp", "led lights", "string lights", "light strip"]},
            {"slug": "room-decor-and-wall-art", "name": "Room Decor & Wall Art", "keywords": ["poster", "rug", "tapestry", "decor", "plants"]},
            {"slug": "mirrors", "name": "Mirrors"},
            {"slug": "kitchen-and-dining", "name": "Kitchen & Dining", "keywords": ["dishes", "cups", "mugs", "pots", "pans", "utensils"]},
            {"slug": "small-appliances", "name": "Small Appliances", "keywords": ["microwave", "mini fridge", "air fryer", "coffee maker", "kettle", "fan"]},
            {"slug": "cleaning-supplies", "name": "Cleaning Supplies", "keywords": ["vacuum", "laundry", "detergent"]},
            {"slug": "other-home-essentials", "name": "Other Home Essentials"},
        ],
    },
    {
        "slug": "books-and-school-supplies",
        "name": "Books & School Supplies",
        "icon": "book",
        "children": [
            {"slug": "textbooks", "name": "Textbooks", "keywords": ["textbook", "course book", "lab manual"]},
            {"slug": "general-books", "name": "General Books", "keywords": ["novel", "book", "fiction", "nonfiction"]},
            {"slug": "notebooks-and-stationery", "name": "Notebooks & Stationery", "keywords": ["notebook", "pens", "planner", "binder", "journal"]},
            {"slug": "calculators", "name": "Calculators", "keywords": ["ti 84", "graphing calculator", "scientific calculator"]},
            {"slug": "backpacks-and-school-bags", "name": "Backpacks & School Bags", "keywords": ["backpack", "book bag", "laptop bag", "tote"]},
            {"slug": "art-and-class-supplies", "name": "Art & Class Supplies", "keywords": ["sketchbook", "markers", "paint", "class supplies"]},
            {"slug": "lab-and-course-equipment", "name": "Lab & Course Equipment", "keywords": ["lab coat", "goggles", "stethoscope", "scrubs"]},
            {"slug": "other-school-supplies", "name": "Other School Supplies"},
        ],
    },
    {
        "slug": "accessories-and-jewelry",
        "name": "Accessories & Jewelry",
        "icon": "gem",
        "children": [
            {"slug": "necklaces-and-chains", "name": "Necklaces & Chains", "keywords": ["necklace", "chain", "pendant"]},
            {"slug": "bracelets", "name": "Bracelets", "keywords": ["bracelet", "bangle", "charm"]},
            {"slug": "rings", "name": "Rings", "keywords": ["ring", "band"]},
            {"slug": "earrings", "name": "Earrings", "keywords": ["earrings", "studs", "hoops"]},
            {"slug": "watches", "name": "Watches", "keywords": ["watch", "wristwatch", "rolex"]},
            {"slug": "handbags-and-purses", "name": "Handbags & Purses", "keywords": ["purse", "handbag", "clutch", "tote", "bag"]},
            {"slug": "wallets-and-card-holders", "name": "Wallets & Card Holders", "keywords": ["wallet", "card holder"]},
            {"slug": "hats-and-headwear", "name": "Hats & Headwear", "keywords": ["hat", "cap", "beanie", "durag", "bonnet", "fitted"]},
            {"slug": "sunglasses", "name": "Sunglasses", "keywords": ["shades", "glasses"]},
            {"slug": "belts", "name": "Belts"},
            {"slug": "other-accessories", "name": "Other Accessories"},
        ],
    },
    {
        "slug": "gaming-and-entertainment",
        "name": "Gaming & Entertainment",
        "icon": "gamepad",
        "children": [
            {"slug": "gaming-consoles", "name": "Gaming Consoles", "keywords": ["playstation", "ps5", "ps4", "xbox", "nintendo", "switch"]},
            {"slug": "video-games", "name": "Video Games", "keywords": ["games", "ps5 game", "xbox game", "switch game"]},
            {"slug": "controllers-and-gaming-accessories", "name": "Controllers & Gaming Accessories", "keywords": ["controller", "headset", "gaming chair"]},
            {"slug": "board-games-and-puzzles", "name": "Board Games & Puzzles", "keywords": ["board game", "cards", "puzzle", "chess"]},
            {"slug": "movies-music-and-physical-media", "name": "Movies, Music & Physical Media", "keywords": ["vinyl", "records", "cd", "dvd", "blu ray"]},
            {"slug": "musical-instruments-and-gear", "name": "Musical Instruments & Gear", "keywords": ["guitar", "keyboard", "piano", "drums", "microphone", "amp"]},
            {"slug": "other-gaming-and-entertainment", "name": "Other Gaming & Entertainment"},
        ],
    },
    {
        "slug": "sports-and-fitness",
        "name": "Sports & Fitness",
        "icon": "dumbbell",
        "children": [
            {"slug": "gym-and-workout-equipment", "name": "Gym & Workout Equipment", "keywords": ["weights", "dumbbells", "yoga mat", "resistance bands"]},
            {"slug": "team-sports-equipment", "name": "Team Sports Equipment", "keywords": ["basketball", "football", "soccer", "baseball", "jersey"]},
            {"slug": "bikes-scooters-and-accessories", "name": "Bikes, Scooters & Accessories", "keywords": ["bike", "bicycle", "scooter", "skateboard", "helmet"]},
            {"slug": "outdoor-and-recreational-gear", "name": "Outdoor & Recreational Gear", "keywords": ["camping", "tent", "hiking", "fishing"]},
            {"slug": "other-sports-and-fitness", "name": "Other Sports & Fitness"},
        ],
    },
    {
        "slug": "art-crafts-and-handmade",
        "name": "Art, Crafts & Handmade",
        "icon": "palette",
        "description": "Handmade clothing and jewelry belong in Clothing or Accessories & Jewelry so buyers find them by item type.",
        "children": [
            {"slug": "paintings-and-prints", "name": "Paintings & Prints", "keywords": ["painting", "print", "canvas", "artwork"]},
            {"slug": "custom-and-personalized-gifts", "name": "Custom & Personalized Gifts", "keywords": ["custom", "personalized", "gift", "engraved"]},
            {"slug": "handmade-decor-and-keepsakes", "name": "Handmade Decor & Keepsakes", "keywords": ["candles", "crochet", "keepsake", "handmade decor"]},
            {"slug": "crafts-and-diy-supplies", "name": "Crafts & DIY Supplies", "keywords": ["yarn", "beads", "fabric", "diy"]},
            {"slug": "other-handmade-items", "name": "Other Handmade Items"},
        ],
    },
    {
        "slug": "beauty-and-personal-care",
        "name": "Beauty & Personal Care",
        "icon": "sparkles",
        "children": [
            {"slug": "skincare", "name": "Skincare", "keywords": ["moisturizer", "cleanser", "serum", "lotion", "sunscreen"]},
            {"slug": "makeup-and-cosmetics", "name": "Makeup & Cosmetics", "keywords": ["makeup", "lipstick", "lip gloss", "foundation", "mascara"]},
            {"slug": "fragrances", "name": "Fragrances", "keywords": ["perfume", "cologne", "body spray"]},
            {"slug": "haircare-products", "name": "Haircare Products", "keywords": ["shampoo", "conditioner", "edge control", "hair oil"]},
            {"slug": "hair-accessories", "name": "Hair Accessories", "keywords": ["scrunchies", "clips", "headbands", "bonnet"]},
            {"slug": "wigs-and-hair-extensions", "name": "Wigs & Hair Extensions", "keywords": ["wig", "bundles", "extensions", "lace front", "braiding hair"]},
            {"slug": "nail-products", "name": "Nail Products", "keywords": ["nails", "press ons", "nail polish"]},
            {"slug": "grooming-tools", "name": "Grooming Tools", "keywords": ["clippers", "trimmer", "razor", "flat iron", "blow dryer"]},
            {"slug": "other-beauty-products", "name": "Other Beauty Products"},
        ],
    },
    {
        "slug": "collectibles-and-memorabilia",
        "name": "Collectibles & Memorabilia",
        "icon": "trophy",
        "children": [
            {
                "slug": "hampton-university-merchandise",
                "name": "Hampton University Merchandise",
                "keywords": ["hampton", "hu", "pirates", "hampton university"],
                "description": "Any Hampton-branded item, including apparel.",
            },
            {"slug": "college-and-hbcu-memorabilia", "name": "College & HBCU Memorabilia", "keywords": ["hbcu", "college", "university", "greek", "homecoming"]},
            {"slug": "trading-cards", "name": "Trading Cards", "keywords": ["pokemon", "sports cards", "yugioh"]},
            {"slug": "vintage-collectibles", "name": "Vintage Collectibles"},
            {"slug": "autographs-and-memorabilia", "name": "Autographs & Memorabilia", "keywords": ["autograph", "signed"]},
            {"slug": "figures-toys-and-display-collectibles", "name": "Figures, Toys & Display Collectibles", "keywords": ["funko", "figure", "action figure", "lego", "toys"]},
            {"slug": "other-collectibles", "name": "Other Collectibles"},
        ],
    },
    {
        "slug": OTHER_SLUG,
        "name": "Other",
        "icon": "box",
        "children": [],
    },
]
