"""
Deterministic business logic for event planning:
- Input validation (guests 1-5000, INR budget, future dates, max 300 char preferences)
- Budget breakdown by event type & per-guest tiers (tight trims decor, grows buffer)
- Timeline counted back from event date flagging past-due tasks
- Vendor checklist with extra security and parking for 200+ guests
- Integration URL builders (Google Calendar, Google Maps)
"""

from datetime import date, datetime, timedelta
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Union

ALLOWED_EVENT_TYPES = ("weddings", "birthdays", "community events")

# Per-guest budget tier thresholds (in INR)
# (tight: < low, comfortable: low <= x <= high, premium: > high)
TIER_THRESHOLDS: Dict[str, Tuple[float, float]] = {
    "weddings": (1500.0, 4000.0),
    "birthdays": (500.0, 1500.0),
    "community events": (250.0, 800.0),
}

# Allocations: percentages must sum to 100 for each (event_type, tier).
# Notice: 'tight' trims decor and grows the contingency buffer.
BUDGET_ALLOCATION_TEMPLATES: Dict[str, Dict[str, Dict[str, float]]] = {
    "weddings": {
        "tight": {
            "Venue & Setup": 38.0,
            "Catering & Drinks": 36.0,
            "Decor & Styling": 5.0,     # Trimmed decor
            "Entertainment & Sound": 5.0,
            "Photography & Video": 4.0,
            "Buffer / Contingency": 12.0,  # Grown buffer
        },
        "comfortable": {
            "Venue & Setup": 32.0,
            "Catering & Drinks": 36.0,
            "Decor & Styling": 15.0,
            "Entertainment & Sound": 6.0,
            "Photography & Video": 6.0,
            "Buffer / Contingency": 5.0,
        },
        "premium": {
            "Venue & Setup": 30.0,
            "Catering & Drinks": 34.0,
            "Decor & Styling": 20.0,
            "Entertainment & Sound": 8.0,
            "Photography & Video": 6.0,
            "Buffer / Contingency": 2.0,
        },
    },
    "birthdays": {
        "tight": {
            "Venue & Seating": 28.0,
            "Food & Beverages": 46.0,
            "Decor & Cake": 5.0,        # Trimmed decor
            "Games & Music": 5.0,
            "Favors & Gifts": 4.0,
            "Buffer / Contingency": 12.0,  # Grown buffer
        },
        "comfortable": {
            "Venue & Seating": 24.0,
            "Food & Beverages": 44.0,
            "Decor & Cake": 15.0,
            "Games & Music": 7.0,
            "Favors & Gifts": 5.0,
            "Buffer / Contingency": 5.0,
        },
        "premium": {
            "Venue & Seating": 22.0,
            "Food & Beverages": 40.0,
            "Decor & Cake": 20.0,
            "Games & Music": 10.0,
            "Favors & Gifts": 6.0,
            "Buffer / Contingency": 2.0,
        },
    },
    "community events": {
        "tight": {
            "Ground / Venue Permissions": 33.0,
            "Refreshments & Water": 35.0,
            "Signage & Basic Decor": 5.0,   # Trimmed decor
            "Stage, Sound & AV": 11.0,
            "Logistics & Sanitation": 4.0,
            "Buffer / Contingency": 12.0,   # Grown buffer
        },
        "comfortable": {
            "Ground / Venue Permissions": 28.0,
            "Refreshments & Water": 35.0,
            "Signage & Basic Decor": 12.0,
            "Stage, Sound & AV": 14.0,
            "Logistics & Sanitation": 6.0,
            "Buffer / Contingency": 5.0,
        },
        "premium": {
            "Ground / Venue Permissions": 26.0,
            "Refreshments & Water": 34.0,
            "Signage & Basic Decor": 18.0,
            "Stage, Sound & AV": 14.0,
            "Logistics & Sanitation": 6.0,
            "Buffer / Contingency": 2.0,
        },
    },
}

# Base vendor checklists per event type
BASE_VENDOR_CHECKLIST: Dict[str, List[Dict[str, str]]] = {
    "weddings": [
        {"category": "Venue", "task": "Book banquet hall / lawn / resort", "search_query": "wedding venue banquet lawn"},
        {"category": "Catering", "task": "Select wedding caterer & finalize multi-course menu", "search_query": "wedding caterers"},
        {"category": "Decor", "task": "Mandap, floral, stage, and entrance lighting decorator", "search_query": "wedding decorator and florist"},
        {"category": "Photography", "task": "Hire candid photographer and cinematic videographer", "search_query": "wedding photographer videographer"},
        {"category": "Entertainment", "task": "Book DJ, sound system, dhol players or live band", "search_query": "wedding DJ sound dhol"},
        {"category": "Bridal & Groom", "task": "Reserve makeup artist, mehndi artist, hair stylist", "search_query": "bridal makeup artist mehndi"},
        {"category": "Invitations", "task": "Print formal invitations and set up digital invites", "search_query": "wedding invitation card printers"},
    ],
    "birthdays": [
        {"category": "Venue", "task": "Reserve party hall, play zone, or restaurant terrace", "search_query": "birthday party hall venue"},
        {"category": "Catering", "task": "Order custom theme cake, snacks, and dinner buffet", "search_query": "bakery custom cakes caterers"},
        {"category": "Decor", "task": "Balloon arches, theme backdrop, and table centerpieces", "search_query": "birthday balloon decorator"},
        {"category": "Entertainment", "task": "Book host/emcee, magician, tattoo artist, or game coordinator", "search_query": "party entertainer magician emcee"},
        {"category": "Photography", "task": "Hire event photographer for family and party photos", "search_query": "event photographer"},
        {"category": "Favors", "task": "Purchase return gifts and party favor boxes", "search_query": "birthday return gifts wholesale"},
    ],
    "community events": [
        {"category": "Venue", "task": "Secure municipal/police ground permission and venue permits", "search_query": "community event hall ground booking"},
        {"category": "Audio/Visual", "task": "Book PA system, microphones, projection screen, stage lighting", "search_query": "PA sound system rental stage lighting"},
        {"category": "Catering", "task": "Arrange packaged water, tea/coffee, and boxed snacks/meals", "search_query": "bulk event catering refreshment snacks"},
        {"category": "Infrastructure", "task": "Rent shamiana, chairs, tables, barricades, and podium", "search_query": "shamiana tent house chair rental"},
        {"category": "Sanitation", "task": "Arrange portable toilets, waste disposal bins, and cleaning crew", "search_query": "portable toilet waste management rental"},
        {"category": "Signage & Print", "task": "Print directional banners, schedule posters, badges", "search_query": "flex banner printing vinyl poster"},
    ],
}


def normalize_event_type(raw_type: str) -> str:
    """
    Normalize event type string to one of the canonical types.
    Raises ValueError if unsupported.
    """
    if not isinstance(raw_type, str):
        raise ValueError("Event type must be a string.")
    
    cleaned = raw_type.strip().lower()
    mapping = {
        "wedding": "weddings",
        "weddings": "weddings",
        "birthday": "birthdays",
        "birthdays": "birthdays",
        "community event": "community events",
        "community events": "community events",
        "community": "community events",
    }
    if cleaned not in mapping:
        allowed = ", ".join(ALLOWED_EVENT_TYPES)
        raise ValueError(f"Invalid event type '{raw_type}'. Supported types: {allowed}")
    return mapping[cleaned]


def validate_input(
    event_type: str,
    guests: Union[int, str],
    budget: Union[float, int, str],
    event_date: Union[str, date],
    preferences: str = "",
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Validate all inputs deterministically:
    - event_type: weddings, birthdays, community events
    - guests: int, 1 to 5000
    - budget: float, > 0 in INR
    - event_date: future date strictly after reference_date (defaults to date.today())
    - preferences: str, max 300 characters
    """
    normalized_type = normalize_event_type(event_type)

    # Validate guests
    try:
        # Prevent boolean being treated as int in Python (isinstance(True, int) is True)
        if isinstance(guests, bool):
            raise ValueError
        parsed_guests = int(guests)
    except (ValueError, TypeError):
        raise ValueError("Guests must be a valid integer between 1 and 5000.")

    if not (1 <= parsed_guests <= 5000):
        raise ValueError(f"Guest count must be between 1 and 5000. Got {parsed_guests}.")

    # Validate budget
    try:
        if isinstance(budget, bool):
            raise ValueError
        parsed_budget = float(budget)
    except (ValueError, TypeError):
        raise ValueError("Budget must be a valid positive number in INR.")

    if parsed_budget <= 0:
        raise ValueError("Budget must be greater than 0 INR.")
    if parsed_budget > 10_000_000_000:  # 1000 crore sanity limit
        raise ValueError("Budget exceeds maximum allowable limit.")

    # Validate event_date
    if reference_date is None:
        ref_date = date.today()
    elif isinstance(reference_date, date):
        ref_date = reference_date
    else:
        raise ValueError("reference_date must be a datetime.date instance.")

    if isinstance(event_date, date):
        parsed_date = event_date
    elif isinstance(event_date, str):
        cleaned_date = event_date.strip()
        try:
            parsed_date = datetime.strptime(cleaned_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Event date must be in YYYY-MM-DD format.")
    else:
        raise ValueError("Event date must be a string (YYYY-MM-DD) or datetime.date object.")

    if parsed_date <= ref_date:
        raise ValueError(
            f"Event date ({parsed_date.isoformat()}) must be in the future (strictly after {ref_date.isoformat()})."
        )

    # Validate preferences
    if preferences is None:
        cleaned_preferences = ""
    elif not isinstance(preferences, str):
        raise ValueError("Preferences must be a string.")
    else:
        cleaned_preferences = preferences.strip()

    if len(cleaned_preferences) > 300:
        raise ValueError(
            f"Preferences must not exceed 300 characters. Currently {len(cleaned_preferences)} characters."
        )

    return {
        "event_type": normalized_type,
        "guests": parsed_guests,
        "budget": round(parsed_budget, 2),
        "event_date": parsed_date,
        "preferences": cleaned_preferences,
        "reference_date": ref_date,
    }


def determine_budget_tier(event_type: str, budget_per_guest: float) -> str:
    """
    Determine budget tier ('tight', 'comfortable', 'premium') based on per-guest budget in INR.
    """
    low, high = TIER_THRESHOLDS[event_type]
    if budget_per_guest < low:
        return "tight"
    if budget_per_guest <= high:
        return "comfortable"
    return "premium"


def calculate_budget_split(event_type: str, guests: int, total_budget: float) -> Dict[str, Any]:
    """
    Split budget across categories based on event type and tier (budget-per-guest).
    'tight' trims decor and expands buffer/contingency.
    Returns exact allocation amounts and percentages summing to 100%.
    """
    norm_type = normalize_event_type(event_type)
    if guests <= 0:
        raise ValueError("Guests must be at least 1.")
    if total_budget <= 0:
        raise ValueError("Budget must be greater than 0.")

    per_guest = total_budget / guests
    tier = determine_budget_tier(norm_type, per_guest)
    template = BUDGET_ALLOCATION_TEMPLATES[norm_type][tier]

    allocations = []
    total_allocated = 0.0

    # Sort categories to ensure deterministic rounding adjustment
    items = list(template.items())
    for category, pct in items[:-1]:
        amt = round((total_budget * pct) / 100.0, 2)
        allocations.append({
            "category": category,
            "percentage": pct,
            "amount_inr": amt,
        })
        total_allocated += amt

    # Ensure last item absorbs any fraction-of-cent rounding discrepancy
    last_cat, last_pct = items[-1]
    last_amt = round(total_budget - total_allocated, 2)
    allocations.append({
        "category": last_cat,
        "percentage": last_pct,
        "amount_inr": last_amt,
    })

    return {
        "tier": tier,
        "budget_per_guest_inr": round(per_guest, 2),
        "total_budget_inr": round(total_budget, 2),
        "currency": "INR",
        "allocations": allocations,
    }


def build_google_calendar_url(title: str, target_date: date, details: str = "") -> str:
    """
    Generate an 'Add to Google Calendar' URL for an all-day event.
    Google Calendar standard template URL format:
    dates=YYYYMMDD/YYYYMMDD (end date is next day for 1-day event).
    """
    start_str = target_date.strftime("%Y%m%d")
    end_date = target_date + timedelta(days=1)
    end_str = end_date.strftime("%Y%m%d")
    
    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_str}/{end_str}",
        "details": details or f"Task for event planning: {title}",
    }
    return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"


def build_google_maps_url(query: str, location_hint: str = "India") -> str:
    """
    Generate a Google Maps search URL for finding local vendors.
    """
    full_query = f"{query} near me {location_hint}".strip()
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(full_query)}"


# Milestone templates: offsets in days before event date (descending)
TIMELINE_MILESTONES: Dict[str, List[Tuple[int, str, str]]] = {
    "weddings": [
        (180, "Set Guest List & Secure Venue", "Finalize estimated count and lock down main wedding venue."),
        (120, "Hire Caterer & Candid Photographer", "Select wedding banquet menu and book photo/video crew."),
        (90, "Book Decorator, Priest/Officiant & DJ", "Finalize stage, mandap, entrance themes, and audio setup."),
        (60, "Send Formal Invitations & Outfits Fitting", "Dispatch physical/digital invites and begin couture fittings."),
        (30, "Confirm Guest RSVPs & Schedule Rehearsal", "Lock guest count with venue caterers and finalize runsheet."),
        (14, "Final Vendor Coordination & Logistics Check", "Confirm arrival times, power backups, and transportation."),
        (3, "Decor Inspection & Rehearsal Walkthrough", "Review hall layout, sound check, and finalize sequence."),
        (0, "Wedding Day Execution", "Oversee host greetings, ceremonies, catering service, and celebration."),
    ],
    "birthdays": [
        (45, "Decide Theme & Reserve Venue", "Pick party theme (colors/characters) and book party space."),
        (30, "Book Caterer, Cake Baker & Entertainer", "Lock custom theme cake, snack menu, magician or emcee."),
        (20, "Send Digital Invites & Track RSVPs", "Distribute RSVP links to family and friends."),
        (10, "Order Decorations, Balloons & Return Gifts", "Procure party favors, banners, and balloon arrangements."),
        (3, "Finalize RSVP Headcount & Food Orders", "Update food portions with caterer and confirm cake delivery slot."),
        (1, "Pick Up Cake & Prep Gift Area", "Verify sound playlist, camera batteries, and party game accessories."),
        (0, "Party Day Coordination", "Setup decor, welcome guests, host games, and cake cutting."),
    ],
    "community events": [
        (90, "Form Committee & Obtain Municipal Permits", "Secure ground usage approvals, police NOC, and fire clearance."),
        (60, "Book Stage, Sound System & Main Caterer", "Lock in stage rigging, PA system, generators, and refreshments."),
        (30, "Launch Public Registrations & Marketing", "Publish flyers, community portal notices, and banner placement."),
        (14, "Logistics, Sanitation & Volunteer Briefing", "Allocate safety marshal duties, waste bins, and first aid booth."),
        (7, "Confirm Registrations & Final Vendor Run-Through", "Review sound permits, electrical line checks, and emergency lanes."),
        (1, "Stage Setup & Equipment Soundcheck", "Erect banners, test microphones, inspect seating rows and barricades."),
        (0, "Event Day Management", "Coordinate attendee entry, stage schedule, refreshment distribution, cleanup."),
    ],
}


def generate_timeline(
    event_date: date,
    reference_date: Optional[date] = None,
    event_type: str = "weddings",
) -> List[Dict[str, Any]]:
    """
    Generate timeline counted back from event_date.
    Flags tasks as 'is_past_due' if target_date < reference_date.
    Also provides precomputed Google Calendar URLs for each task.
    """
    norm_type = normalize_event_type(event_type)
    ref = reference_date if reference_date is not None else date.today()

    milestones = TIMELINE_MILESTONES.get(norm_type, TIMELINE_MILESTONES["weddings"])
    timeline_tasks = []

    for days_before, title, description in milestones:
        target_date = event_date - timedelta(days=days_before)
        is_past_due = target_date < ref
        
        cal_url = build_google_calendar_url(
            title=f"[{norm_type.title()}] {title}",
            target_date=target_date,
            details=f"{description} (Target: T-{days_before} days before event on {event_date.isoformat()})",
        )

        timeline_tasks.append({
            "days_before_event": days_before,
            "title": title,
            "description": description,
            "target_date": target_date.isoformat(),
            "is_past_due": is_past_due,
            "status": "Past Due" if is_past_due else "Upcoming",
            "google_calendar_url": cal_url,
        })

    return timeline_tasks


def generate_vendor_checklist(
    event_type: str,
    guests: int,
    location_hint: str = "India",
) -> List[Dict[str, Any]]:
    """
    Generate vendor checklist.
    For 200+ guests, includes mandatory extra security and valet/parking management.
    Includes Google Maps search URLs for each vendor category.
    """
    norm_type = normalize_event_type(event_type)
    checklist: List[Dict[str, Any]] = []

    base_items = BASE_VENDOR_CHECKLIST.get(norm_type, BASE_VENDOR_CHECKLIST["weddings"])
    for item in base_items:
        checklist.append({
            "category": item["category"],
            "task": item["task"],
            "mandatory": False,
            "google_maps_url": build_google_maps_url(item["search_query"], location_hint),
        })

    # Requirement: extra security/parking for 200+ guests
    if guests >= 200:
        checklist.append({
            "category": "Dedicated Security & Bouncers",
            "task": f"Mandatory for large gathering ({guests} guests): Deploy licensed security guards for crowd control, perimeter patrol, and VIP safety.",
            "mandatory": True,
            "google_maps_url": build_google_maps_url("event security bouncers agency", location_hint),
        })
        checklist.append({
            "category": "Valet & Parking Marshals",
            "task": f"Mandatory for high traffic ({guests} guests): Reserve designated parking lot, contract valet drivers, and assign traffic marshals.",
            "mandatory": True,
            "google_maps_url": build_google_maps_url("valet parking service event traffic management", location_hint),
        })

    return checklist


def generate_plan(
    event_type: str,
    guests: Union[int, str],
    budget: Union[float, int, str],
    event_date: Union[str, date],
    preferences: str = "",
    reference_date: Optional[date] = None,
    location_hint: str = "India",
) -> Dict[str, Any]:
    """
    Full deterministic plan generator:
    Validates input, computes tiered budget breakdown, creates timeline with past-due flags,
    and builds vendor checklist with safety/parking provisions for 200+ guests.
    """
    validated = validate_input(
        event_type=event_type,
        guests=guests,
        budget=budget,
        event_date=event_date,
        preferences=preferences,
        reference_date=reference_date,
    )

    budget_plan = calculate_budget_split(
        event_type=validated["event_type"],
        guests=validated["guests"],
        total_budget=validated["budget"],
    )

    timeline = generate_timeline(
        event_date=validated["event_date"],
        reference_date=validated["reference_date"],
        event_type=validated["event_type"],
    )

    vendor_checklist = generate_vendor_checklist(
        event_type=validated["event_type"],
        guests=validated["guests"],
        location_hint=location_hint,
    )

    return {
        "inputs": {
            "event_type": validated["event_type"],
            "guests": validated["guests"],
            "budget": validated["budget"],
            "currency": "INR",
            "event_date": validated["event_date"].isoformat(),
            "preferences": validated["preferences"],
        },
        "budget_plan": budget_plan,
        "timeline": timeline,
        "vendor_checklist": vendor_checklist,
    }
