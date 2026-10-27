
BEGIN;

-- Create three demo users. Passwords are deliberately unusable:
-- these are display-only test accounts, not login credentials.
INSERT INTO users (username, password, email)
VALUES
  ('demo_pirate_threads', '!demo-no-login!', 'piratethreads@example.invalid'),
  ('demo_757_streetwear', '!demo-no-login!', '757streetwear@example.invalid'),
  ('demo_campus_collective', '!demo-no-login!', 'campuscollective@example.invalid');

-- Create the brands and associate each with its owner.
INSERT INTO storefronts (owner_id, brand_name, bio, categories)
SELECT id, 'Pirate Threads',
       'Hampton-inspired everyday streetwear.',
       'T-Shirts & Tops, Hoodies & Sweatshirts'
FROM users WHERE username = 'demo_pirate_threads';

INSERT INTO storefronts (owner_id, brand_name, bio, categories)
SELECT id, '757 Streetwear',
       'Original streetwear inspired by Hampton Roads.',
       'Jackets & Coats, Jeans & Pants'
FROM users WHERE username = 'demo_757_streetwear';

INSERT INTO storefronts (owner_id, brand_name, bio, categories)
SELECT id, 'Campus Collective',
       'Comfortable, creative styles for campus life.',
       'T-Shirts & Tops, Shorts'
FROM users WHERE username = 'demo_campus_collective';

-- Add two clothing products to each brand.
INSERT INTO listings
    (storefront_id, title, description, price,
     fulfillment_type, quantity_on_hand, category_id)
SELECT s.id, p.title, p.description, p.price,
       'IN_STOCK', 10, p.category_id
FROM (
    VALUES
      ('Pirate Threads', 'Pirate Classic Tee',
       'Everyday graphic T-shirt.', 25.00, 13),
      ('Pirate Threads', 'Hampton Hoodie',
       'Comfortable campus-inspired hoodie.', 55.00, 14),
      ('757 Streetwear', '757 Denim Jacket',
       'Classic streetwear denim jacket.', 75.00, 15),
      ('757 Streetwear', '757 Cargo Pants',
       'Relaxed-fit utility cargo pants.', 48.00, 16),
      ('Campus Collective', 'Campus Graphic Tee',
       'Original campus graphic T-shirt.', 28.00, 13),
      ('Campus Collective', 'Everyday Shorts',
       'Comfortable casual shorts.', 32.00, 17)
) AS p(brand_name, title, description, price, category_id)
JOIN storefronts s ON s.brand_name = p.brand_name;

COMMIT;
