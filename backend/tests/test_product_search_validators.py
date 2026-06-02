import unittest

from app.models.schemas import ProductResult, StoreName
from app.services.product_search_service import ProductSearchService
from app.services.product_search_validators import parse_search_intent, validate_product


class ProductSearchValidatorTests(unittest.TestCase):
    def test_parse_search_intent_extracts_puff_bag_details(self):
        intent = parse_search_intent("puff bag outdoors red under $20")

        self.assertEqual(intent.max_price, 20)
        self.assertIn("red", intent.colors)
        self.assertIn("puff bag", intent.product_phrases)
        self.assertIn("backpack", intent.excluded_terms)
        self.assertIn("puff", intent.synonym_groups)

    def test_parse_search_intent_extracts_range_budget_upper_bound(self):
        intent = parse_search_intent("tall indoor white and yellow vase under around 70-120$")

        self.assertEqual(intent.max_price, 120)

    def test_rejects_backpack_for_puff_bag_intent(self):
        intent = parse_search_intent("puff bag outdoors red under $20")
        product = ProductResult(
            store=StoreName.EBAY,
            title="Under Armour UA Storm Hustle Backpack Book Bag Black Red",
            link="https://www.ebay.com/itm/123",
            price=16,
            score=0.75,
        )

        decision = validate_product(intent, product)

        self.assertFalse(decision.accepted)
        self.assertIn("backpack", decision.reasons[0])

    def test_rejects_furniture_beanbag_for_puff_bag_intent(self):
        intent = parse_search_intent("puff bag outdoors red under $20")
        product = ProductResult(
            store=StoreName.AMAZON,
            title="Large Lazy Sofa Chair Bean Bag Pouf Puff Couch Red",
            link="https://www.amazon.com/example/dp/B000000000/",
            price=18.8,
            score=0.75,
        )

        decision = validate_product(intent, product)

        self.assertFalse(decision.accepted)
        self.assertIn("bean bag", decision.reasons[0])

    def test_rejects_cosmetic_bag_for_puff_bag_intent(self):
        intent = parse_search_intent("puff bag outdoors red under $20")
        product = ProductResult(
            store=StoreName.AMAZON,
            title="Puffy Padded Makeup Cosmetic Bag Garnet Red",
            link="https://www.amazon.com/example/dp/B000000001/",
            price=16.99,
            score=0.75,
        )

        decision = validate_product(intent, product)

        self.assertFalse(decision.accepted)
        self.assertIn("rejected category term", decision.reasons[0])

    def test_rejects_result_with_only_snippet_puffer_match(self):
        intent = parse_search_intent("puff bag outdoors red under $20")
        product = ProductResult(
            store=StoreName.TARGET,
            title="Game Day Clear Crossbody Bag - Wild Fable Dark Red",
            description="Related item: Puffer Crossbody Handbag - Wild Fable.",
            link="https://www.target.com/p/game-day-clear-crossbody-bag/-/A-94269203",
            price=20,
            score=0.75,
        )

        decision = validate_product(intent, product)

        self.assertFalse(decision.accepted)
        self.assertIn("missing required puff signal", decision.reasons[0])

    def test_rejects_food_puffs_for_puff_bag_intent(self):
        intent = parse_search_intent("puff bag outdoors red under $20")
        product = ProductResult(
            store=StoreName.EBAY,
            title="Red Bird Soft Peppermint Candy Puffs 4 oz Bag",
            link="https://www.ebay.com/itm/456",
            price=13.99,
            score=0.75,
        )

        decision = validate_product(intent, product)

        self.assertFalse(decision.accepted)
        self.assertIn("candy", decision.reasons[0])

    def test_accepts_matching_red_puffer_bag(self):
        intent = parse_search_intent("puff bag outdoors red under $20")
        product = ProductResult(
            store=StoreName.TARGET,
            title="Puffer Hobo Shoulder Bag - Wild Fable Red",
            description="Boxed puffer design with lightweight recycled polyester.",
            link="https://www.target.com/p/puffer-hobo-bag-wild-fable-red/-/A-90862913",
            price=17.5,
            image="https://example.com/image.jpg",
            rating=4.7,
            reviews=418,
            score=0.875,
        )

        decision = validate_product(intent, product)

        self.assertTrue(decision.accepted)
        self.assertGreater(decision.score_adjustment, 0)

    def test_rejects_coffee_table_accessory_tray(self):
        intent = parse_search_intent("small round wooden coffee table under $100")
        product = ProductResult(
            store=StoreName.AMAZON,
            title="Candle Holder Tray Home Decor, Round Wood Tray for Coffee Table",
            link="https://www.amazon.com/example/dp/B000000002/",
            price=9.99,
            score=0.75,
        )

        decision = validate_product(intent, product)

        self.assertFalse(decision.accepted)
        self.assertIn("rejected category term", decision.reasons[0])

    def test_accepts_matching_wooden_coffee_table(self):
        intent = parse_search_intent("small round wooden coffee table under $100")
        product = ProductResult(
            store=StoreName.AMAZON,
            title="Small Round Coffee Table Wooden Surface Top Walnut",
            link="https://www.amazon.com/example/dp/B000000003/",
            price=49.99,
            score=0.75,
        )

        decision = validate_product(intent, product)

        self.assertTrue(decision.accepted)
        self.assertGreater(decision.score_adjustment, 0)


class ProductSearchServiceValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_products_filters_invalid_normalized_results(self):
        service = ProductSearchService()
        service.api_key = "test"

        bad_product = ProductResult(
            store=StoreName.EBAY,
            title="Under Armour UA Storm Hustle Backpack Book Bag Black Red",
            link="https://www.ebay.com/itm/123",
            price=16,
            score=0.75,
        )
        original_good_score = 0.875
        good_product = ProductResult(
            store=StoreName.TARGET,
            title="Puffer Hobo Shoulder Bag - Wild Fable Red",
            description="Boxed puffer design with zippered main compartment.",
            link="https://www.target.com/p/puffer-hobo-bag-wild-fable-red/-/A-90862913",
            price=17.5,
            image="https://example.com/image.jpg",
            score=original_good_score,
        )
        duplicate_good_product = ProductResult(
            store=StoreName.TARGET,
            title="Puffer Hobo Shoulder Bag - Wild Fable Red",
            description="Same product under a different URL.",
            link="https://www.target.com/p/puffer-hobo-bag-wild-fable-red/-/A-00000000",
            price=17.5,
            image="https://example.com/image.jpg",
            score=original_good_score,
        )

        async def fake_search_store(**kwargs):
            store = kwargs["store"]
            if store == StoreName.EBAY:
                return store, [bad_product], None
            return store, [good_product, duplicate_good_product], None

        service._search_store = fake_search_store

        results, errors = await service.search_products(
            description="puff bag outdoors red under $20",
            stores=[StoreName.EBAY, StoreName.TARGET],
            limit_per_store=10,
        )

        self.assertEqual(errors, [])
        self.assertEqual([product.title for product in results], [good_product.title])
        self.assertGreater(results[0].score, original_good_score)


if __name__ == "__main__":
    unittest.main()
