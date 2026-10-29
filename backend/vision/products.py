"""The products the detector is trained to recognize, and the category of each one.

A product's position in PRODUCTS is its YOLO class id, so the dataset labels (SR-57) and the
trained model (SR-59) depend on this order. Only append new products at the end: inserting,
reordering or removing one shifts the ids and silently breaks an already-trained model.
"""
from dataclasses import dataclass
from enum import Enum


class Category(str, Enum):
    # The value is what gets stored in Inventory.category
    DAIRY = "Dairy"
    VEGETABLES = "Vegetables"
    FRUIT = "Fruit"
    MEAT = "Meat"
    DRINKS = "Drinks"
    SPREADS_AND_SAUCES = "Spreads & Sauces"


@dataclass(frozen=True)
class Product:
    # YOLO class name and Inventory.product_name: lowercase English, no spaces
    name: str
    # Display name in the app
    name_he: str
    category: Category


PRODUCTS: tuple[Product, ...] = (
    # Eggs are under Dairy, the same as in Israeli supermarkets
    Product("milk", "חלב", Category.DAIRY),
    Product("yogurt", "יוגורט", Category.DAIRY),
    Product("cottage_cheese", "קוטג'", Category.DAIRY),
    Product("white_cheese", "גבינה לבנה", Category.DAIRY),
    Product("yellow_cheese", "גבינה צהובה", Category.DAIRY),
    Product("butter", "חמאה", Category.DAIRY),
    Product("eggs", "ביצים", Category.DAIRY),
    Product("tomato", "עגבנייה", Category.VEGETABLES),
    Product("cucumber", "מלפפון", Category.VEGETABLES),
    Product("bell_pepper", "פלפל", Category.VEGETABLES),
    Product("carrot", "גזר", Category.VEGETABLES),
    Product("lettuce", "חסה", Category.VEGETABLES),
    Product("apple", "תפוח", Category.FRUIT),
    Product("orange", "תפוז", Category.FRUIT),
    Product("lemon", "לימון", Category.FRUIT),
    Product("grapes", "ענבים", Category.FRUIT),
    Product("strawberries", "תותים", Category.FRUIT),
    Product("chicken", "עוף", Category.MEAT),
    Product("deli_meat", "נקניק", Category.MEAT),
    Product("hot_dogs", "נקניקיות", Category.MEAT),
    Product("soft_drink", "משקה מוגז", Category.DRINKS),
    Product("juice", "מיץ", Category.DRINKS),
    Product("water_bottle", "בקבוק מים", Category.DRINKS),
    Product("hummus", "חומוס", Category.SPREADS_AND_SAUCES),
    Product("ketchup", "קטשופ", Category.SPREADS_AND_SAUCES),
    Product("mayonnaise", "מיונז", Category.SPREADS_AND_SAUCES),
)

PRODUCTS_BY_NAME: dict[str, Product] = {product.name: product for product in PRODUCTS}
# A duplicate name would give two class ids the same label
assert len(PRODUCTS_BY_NAME) == len(PRODUCTS), "duplicate product name in PRODUCTS"


def yolo_class_names() -> list[str]:
    """Class names in class-id order, for the `names` list of the YOLO dataset's data.yaml."""
    return [product.name for product in PRODUCTS]


def category_of(name: str) -> Category | None:
    """The category of a detected product label, or None if the label is unknown."""
    product = PRODUCTS_BY_NAME.get(name)
    return product.category if product else None
