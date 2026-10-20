"""
Unit tests for deterministic event planning logic (planner/logic.py).
Covers validation boundaries, budget tiers, timeline past-due calculation,
and vendor checklists for large gatherings.
"""

from datetime import date, timedelta
import unittest
import urllib.parse

from planner.logic import (
    ALLOWED_EVENT_TYPES,
    build_google_calendar_url,
    build_google_maps_url,
    calculate_budget_split,
    determine_budget_tier,
    generate_plan,
    generate_timeline,
    generate_vendor_checklist,
    normalize_event_type,
    validate_input,
)


class TestValidationLogic(unittest.TestCase):
    """Test validation and normalization rules."""

    def setUp(self):
        self.ref_date = date(2026, 11, 1)
        self.future_date = date(2027, 2, 1)

    def test_normalize_event_type_valid(self):
        self.assertEqual(normalize_event_type("wedding"), "weddings")
        self.assertEqual(normalize_event_type("WEDDINGS"), "weddings")
        self.assertEqual(normalize_event_type("Birthday"), "birthdays")
        self.assertEqual(normalize_event_type("birthdays"), "birthdays")
        self.assertEqual(normalize_event_type("community event"), "community events")
        self.assertEqual(normalize_event_type("Community Events"), "community events")

    def test_normalize_event_type_invalid(self):
        with self.assertRaises(ValueError):
            normalize_event_type("concert")
        with self.assertRaises(ValueError):
            normalize_event_type("")
        with self.assertRaises(ValueError):
            normalize_event_type(123)  # type: ignore

    def test_validate_input_valid(self):
        res = validate_input(
            event_type="wedding",
            guests=150,
            budget=500000,
            event_date="2027-02-01",
            preferences="Traditional North Indian cuisine, no loud music after 10 PM.",
            reference_date=self.ref_date,
        )
        self.assertEqual(res["event_type"], "weddings")
        self.assertEqual(res["guests"], 150)
        self.assertEqual(res["budget"], 500000.0)
        self.assertEqual(res["event_date"], date(2027, 2, 1))
        self.assertEqual(res["preferences"], "Traditional North Indian cuisine, no loud music after 10 PM.")

    def test_guests_boundaries(self):
        # 1 and 5000 are valid boundaries
        res_min = validate_input("birthdays", 1, 10000, self.future_date, reference_date=self.ref_date)
        self.assertEqual(res_min["guests"], 1)

        res_max = validate_input("community events", 5000, 500000, self.future_date, reference_date=self.ref_date)
        self.assertEqual(res_max["guests"], 5000)

        # 0 and 5001 are invalid boundaries
        with self.assertRaises(ValueError):
            validate_input("birthdays", 0, 10000, self.future_date, reference_date=self.ref_date)

        with self.assertRaises(ValueError):
            validate_input("community events", 5001, 500000, self.future_date, reference_date=self.ref_date)

        # Negative and non-integer
        with self.assertRaises(ValueError):
            validate_input("birthdays", -10, 10000, self.future_date, reference_date=self.ref_date)

        with self.assertRaises(ValueError):
            validate_input("birthdays", "five", 10000, self.future_date, reference_date=self.ref_date)

        with self.assertRaises(ValueError):
            validate_input("birthdays", True, 10000, self.future_date, reference_date=self.ref_date)

    def test_budget_boundaries(self):
        # 0 or negative budget is invalid
        with self.assertRaises(ValueError):
            validate_input("weddings", 50, 0, self.future_date, reference_date=self.ref_date)

        with self.assertRaises(ValueError):
            validate_input("weddings", 50, -500, self.future_date, reference_date=self.ref_date)

        with self.assertRaises(ValueError):
            validate_input("weddings", 50, "free", self.future_date, reference_date=self.ref_date)

        with self.assertRaises(ValueError):
            validate_input("weddings", 50, False, self.future_date, reference_date=self.ref_date)

        # Valid positive budget
        res = validate_input("weddings", 50, "150000.50", self.future_date, reference_date=self.ref_date)
        self.assertEqual(res["budget"], 150000.50)

    def test_future_date_validation(self):
        # Past date
        past_date = self.ref_date - timedelta(days=1)
        with self.assertRaises(ValueError):
            validate_input("weddings", 50, 100000, past_date, reference_date=self.ref_date)

        # Same date as reference date (must be strictly in future)
        with self.assertRaises(ValueError):
            validate_input("weddings", 50, 100000, self.ref_date, reference_date=self.ref_date)

        # Invalid format string
        with self.assertRaises(ValueError):
            validate_input("weddings", 50, 100000, "15-12-2027", reference_date=self.ref_date)

        # Valid future string
        future_str = (self.ref_date + timedelta(days=30)).strftime("%Y-%m-%d")
        res = validate_input("weddings", 50, 100000, future_str, reference_date=self.ref_date)
        self.assertEqual(res["event_date"], self.ref_date + timedelta(days=30))

    def test_preferences_length_boundary(self):
        # Exactly 300 characters is allowed
        exact_300 = "a" * 300
        res = validate_input("weddings", 50, 100000, self.future_date, preferences=exact_300, reference_date=self.ref_date)
        self.assertEqual(len(res["preferences"]), 300)

        # 301 characters is rejected
        too_long_301 = "a" * 301
        with self.assertRaises(ValueError):
            validate_input("weddings", 50, 100000, self.future_date, preferences=too_long_301, reference_date=self.ref_date)

        # Empty / None is allowed
        res_none = validate_input("weddings", 50, 100000, self.future_date, preferences=None, reference_date=self.ref_date)
        self.assertEqual(res_none["preferences"], "")


class TestBudgetCalculationLogic(unittest.TestCase):
    """Test budget tiers and allocations."""

    def test_budget_tiers_thresholds(self):
        # Weddings: <1500 tight, 1500-4000 comfortable, >4000 premium
        self.assertEqual(determine_budget_tier("weddings", 1499.0), "tight")
        self.assertEqual(determine_budget_tier("weddings", 1500.0), "comfortable")
        self.assertEqual(determine_budget_tier("weddings", 4000.0), "comfortable")
        self.assertEqual(determine_budget_tier("weddings", 4000.01), "premium")

        # Birthdays: <500 tight, 500-1500 comfortable, >1500 premium
        self.assertEqual(determine_budget_tier("birthdays", 499.0), "tight")
        self.assertEqual(determine_budget_tier("birthdays", 500.0), "comfortable")
        self.assertEqual(determine_budget_tier("birthdays", 1500.0), "comfortable")
        self.assertEqual(determine_budget_tier("birthdays", 1501.0), "premium")

        # Community events: <250 tight, 250-800 comfortable, >800 premium
        self.assertEqual(determine_budget_tier("community events", 249.0), "tight")
        self.assertEqual(determine_budget_tier("community events", 250.0), "comfortable")
        self.assertEqual(determine_budget_tier("community events", 800.0), "comfortable")
        self.assertEqual(determine_budget_tier("community events", 801.0), "premium")

    def test_tight_trims_decor_and_grows_buffer(self):
        """
        Verify the explicit requirement:
        'tight trims decor and grows the buffer'
        """
        for event_type in ALLOWED_EVENT_TYPES:
            # Generate tight tier (low budget per guest)
            tight_plan = calculate_budget_split(event_type=event_type, guests=100, total_budget=10000)
            self.assertEqual(tight_plan["tier"], "tight")

            # Generate comfortable tier (medium budget per guest)
            comf_budget = 300000 if event_type == "weddings" else 100000 if event_type == "birthdays" else 50000
            comf_plan = calculate_budget_split(event_type=event_type, guests=100, total_budget=comf_budget)
            self.assertEqual(comf_plan["tier"], "comfortable")

            tight_allocs = {a["category"]: a["percentage"] for a in tight_plan["allocations"]}
            comf_allocs = {a["category"]: a["percentage"] for a in comf_plan["allocations"]}

            # Find decor category and buffer category
            tight_decor = [pct for cat, pct in tight_allocs.items() if "decor" in cat.lower() or "styling" in cat.lower() or "signage" in cat.lower()][0]
            comf_decor = [pct for cat, pct in comf_allocs.items() if "decor" in cat.lower() or "styling" in cat.lower() or "signage" in cat.lower()][0]

            tight_buffer = [pct for cat, pct in tight_allocs.items() if "buffer" in cat.lower()][0]
            comf_buffer = [pct for cat, pct in comf_allocs.items() if "buffer" in cat.lower()][0]

            # Decor is trimmed in tight tier
            self.assertLess(tight_decor, comf_decor, f"Decor was not trimmed in {event_type}")
            # Buffer is grown in tight tier
            self.assertGreater(tight_buffer, comf_buffer, f"Buffer was not grown in {event_type}")

    def test_allocation_sums_equal_total_budget(self):
        """Percentages must sum to 100, and amounts must equal total budget exactly."""
        test_cases = [
            ("weddings", 250, 750000.75),
            ("birthdays", 35, 45230.0),
            ("community events", 1200, 185000.0),
            ("weddings", 500, 50000.0),  # very tight
        ]
        for event_type, guests, total in test_cases:
            res = calculate_budget_split(event_type, guests, total)
            sum_pct = sum(a["percentage"] for a in res["allocations"])
            sum_amt = sum(a["amount_inr"] for a in res["allocations"])

            self.assertAlmostEqual(sum_pct, 100.0, places=2)
            self.assertAlmostEqual(sum_amt, total, places=2)


class TestTimelineLogic(unittest.TestCase):
    """Test timeline milestone generation and past-due detection."""

    def test_timeline_past_due_flags(self):
        ref_date = date(2026, 11, 1)
        # Event is in 20 days: tasks with milestone > 20 days must be past due
        event_date = ref_date + timedelta(days=20)
        timeline = generate_timeline(event_date=event_date, reference_date=ref_date, event_type="birthdays")

        for task in timeline:
            days_before = task["days_before_event"]
            if days_before > 20:
                self.assertTrue(task["is_past_due"], f"Task T-{days_before} should be flagged past-due")
                self.assertEqual(task["status"], "Past Due")
            else:
                self.assertFalse(task["is_past_due"], f"Task T-{days_before} should not be past-due")
                self.assertEqual(task["status"], "Upcoming")

    def test_google_calendar_url_generation(self):
        target = date(2027, 3, 15)
        url = build_google_calendar_url("Book Caterer", target, "Finalize menu")
        self.assertTrue(url.startswith("https://calendar.google.com/calendar/render?"))
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)

        self.assertEqual(params["action"], ["TEMPLATE"])
        self.assertEqual(params["text"], ["Book Caterer"])
        # Dates should be YYYYMMDD/YYYYMMDD with end date being next day (20270316)
        self.assertEqual(params["dates"], ["20270315/20270316"])
        self.assertEqual(params["details"], ["Finalize menu"])


class TestVendorChecklistLogic(unittest.TestCase):
    """Test vendor checklist with security/parking rules."""

    def test_under_200_guests_no_extra_security_parking(self):
        checklist_199 = generate_vendor_checklist("weddings", guests=199)
        categories = [item["category"] for item in checklist_199]
        self.assertNotIn("Dedicated Security & Bouncers", categories)
        self.assertNotIn("Valet & Parking Marshals", categories)

    def test_200_plus_guests_includes_extra_security_parking(self):
        # Exactly 200 guests
        checklist_200 = generate_vendor_checklist("weddings", guests=200)
        categories = [item["category"] for item in checklist_200]
        self.assertIn("Dedicated Security & Bouncers", categories)
        self.assertIn("Valet & Parking Marshals", categories)

        # 1500 guests
        checklist_1500 = generate_vendor_checklist("community events", guests=1500)
        sec_items = [i for i in checklist_1500 if "Security" in i["category"]]
        self.assertTrue(len(sec_items) > 0)
        self.assertTrue(sec_items[0]["mandatory"])

    def test_google_maps_search_link(self):
        url = build_google_maps_url("wedding caterers", "Mumbai")
        self.assertTrue(url.startswith("https://www.google.com/maps/search/?api=1&query="))
        self.assertIn("wedding+caterers+near+me+Mumbai", url)


class TestFullPlanGeneration(unittest.TestCase):
    """Test end-to-end plan generation."""

    def test_full_plan_structure(self):
        plan = generate_plan(
            event_type="community events",
            guests=350,
            budget=250000,
            event_date="2027-01-15",
            preferences="Water stations and eco-friendly food plates.",
            reference_date=date(2026, 11, 1),
        )
        self.assertIn("inputs", plan)
        self.assertIn("budget_plan", plan)
        self.assertIn("timeline", plan)
        self.assertIn("vendor_checklist", plan)

        # 350 guests => mandatory security & valet
        categories = [v["category"] for v in plan["vendor_checklist"]]
        self.assertIn("Dedicated Security & Bouncers", categories)
        self.assertIn("Valet & Parking Marshals", categories)


if __name__ == "__main__":
    unittest.main()
