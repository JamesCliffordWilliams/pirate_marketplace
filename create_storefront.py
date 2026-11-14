## Iteration 4 - 11/11/26
# Madison Rickman - Creating the ability to create a mock storefront for testing locally

import random

from db import get_connection

def create_storefronts():
    conn = get_connection()
    cur = conn.cursor()

    try:

        #Delete existing user to make a new test one
        cur.execute("DELETE FROM users WHERE email = %s;", ("example@my.hamptonu.edu",))

        owner_id = random.randint(0, 999)
        username = "hello" + str(owner_id)
        brand_name = "Demo Brand"
        #category_choices = []

        # Add a demo user for the storefront
        cur.execute(
            """
            INSERT INTO users (id, username, password, email)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (owner_id, username, "World", "example@my.hamptonu.edu",),
        )
        conn.commit()
        row = cur.fetchone()

        if row:
            storefront_id = random.randint(0, 999)
        #Create a demo storefront
            cur.execute(
                            """
                            INSERT INTO storefronts
                                (id, owner_id, brand_name, bio, logo_url, banner_url, contact_info, preview_image_1, preview_image_2,
                                preview_image_3, preview_image_4, categories, is_active)
                            VALUES
                                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING id, owner_id, brand_name, bio, logo_url, banner_url, contact_info,
                                preview_image_1, preview_image_2, preview_image_3, preview_image_4,
                                categories, is_active, created_at, updated_at
                            """,
                            (
                                storefront_id,
                                owner_id,
                                brand_name,
                                "Sample storefront.",
                                f"https://example.com/logo-url.png",
                                f"https://example.com/banner-url.png",
                                "A random number - contact info",
                                f"https://example.com/preview-image-1.png",
                                f"https://example.com/preview-image-2.png",
                                f"https://example.com/preview-image-3.png",
                                f"https://example.com/preview-image-4.png",
                                'A random category - categories',
                                "TRUE",
                            ),
                        )
        
        conn.commit()
        print("Successfully created a demo user and storefront.")

    except Exception as e:
        conn.rollback()
        print("Error creating a user and storefront: ", e)

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_storefronts()

            

        

