# By Elali McNair - Iteration 4


"""
create_listings.py

Purpose:
Create 1 listing for each existing active storefront in the database.

Run this script manually when:
- You want to populate listings for all storefronts without altering mock_data.py
- Testing storefront views with real data
"""

#Edited to enable local image hosting - Madison Rickman
"""
The image hosting is intended to reach a json file named Local_images that exists on the same folder level as create_listings.
The json file is assumed to have a list inside of an object as such: {"example_list": ["item_1", "item_n"]}
The code assumes that the path to the images has been hardcoded correctly in this file, and if it cannot find it, then it moves on
"""

from pathlib import Path
import json
import random
from db import get_connection


def create_listings_for_storefronts():
    conn = get_connection()
    cur = conn.cursor()
    script_dir = Path(__file__).parent

    try:
        # Query all active storefronts
        cur.execute("SELECT id FROM storefronts WHERE is_active = TRUE;")
        storefront_ids = [row[0] for row in cur.fetchall()]
        print("Current storefronts", storefront_ids)

        if not storefront_ids:
            print("No active storefronts found. Run create_storefront.py first to create storefronts.")
            return

        images_list = []

        try:
            config_path = script_dir / "Local_images.json"
            with open(config_path, "r") as file:
                data = json.load(file)
                images_list = data["Local_images_list"]
                

        except Exception as e:
            print("Could not find local images: ", e)



        # For each storefront, create 1 listing
        for i, storefront_id in enumerate(storefront_ids):
            title = f"Listing for Storefront {storefront_id}"
            cur.execute(
                """
                INSERT INTO listings
                    (storefront_id, title, description, price, fulfillment_type, quantity_on_hand, sizes_available, status)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    storefront_id,
                    title,
                    f"Sample listing description for storefront {storefront_id}.",
                    25.00 + i * 5,  # Vary prices slightly
                    "IN_STOCK",
                    10,
                    '["S","M","L","XL"]',
                    "ACTIVE",
                ),
            )

            row = cur.fetchone()
            if row:
                listing_id = row[0]

                # Add a primary image
                #If images_list was not successfuly populated, use dummy line of code
                #Otherwise, use an image from the list
                if not images_list:
                    cur.execute(
                        """
                        INSERT INTO listing_images (listing_id, image_url, is_primary)
                        VALUES (%s, %s, %s);
                        """,
                        (listing_id, f"https://example.com/listing-{listing_id}.png", True),
                    )
                else:
                    image = random.choice(images_list)
                    print("Current image: ", image)
                    cur.execute(
                        """
                        INSERT INTO listing_images (listing_id, image_url, is_primary)
                        VALUES (%s, %s, %s);
                        """,
                        (listing_id, image, True),
                    )

                # Add sizes
                sizes = [("S", 2), ("M", 3), ("L", 3), ("XL", 2)]
                for size, qty in sizes:
                    cur.execute(
                        """
                        INSERT INTO listing_sizes (listing_id, size, quantity)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (listing_id, size)
                        DO UPDATE SET quantity = EXCLUDED.quantity;
                        """,
                        (listing_id, size, qty),
                    )

        conn.commit()
        print(f"Created 1 listing for each of {len(storefront_ids)} storefronts.")

    except Exception as e:
        conn.rollback()
        print("Error creating listings:", e)

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    create_listings_for_storefronts()