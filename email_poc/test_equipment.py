"""
Test equipment extraction against real notes.
"""

from analyze_notes import fetch_notes
from equipment_extractor import extract_equipment_from_all_notes


def main():
    print("Fetching notes...")
    notes = fetch_notes()
    print(f"Found {len(notes)} notes\n")

    results = extract_equipment_from_all_notes(notes)

    # Display per-note results
    print("=" * 70)
    print("EQUIPMENT FOUND PER NOTE")
    print("=" * 70)
    for r in results:
        print(f"\n--- {r['date']} ---")
        print(f"Subject: {r['subject']}")
        for eq in r["equipments"]:
            print(f"  [{eq.category.upper():12s}] {eq.display_name}")
            if eq.serial:
                print(f"               SN: {eq.serial}")
            if eq.details:
                for d in eq.details[:3]:
                    print(f"               > {d}")
                if len(eq.details) > 3:
                    print(f"               ... +{len(eq.details)-3} more")

    # Summary: unique equipment inventory
    print("\n" + "=" * 70)
    print("EQUIPMENT INVENTORY (all devices seen)")
    print("=" * 70)

    inventory = {}
    for r in results:
        for eq in r["equipments"]:
            key = eq.label
            if key not in inventory:
                inventory[key] = {
                    "equipment": eq,
                    "count": 0,
                    "dates": [],
                }
            inventory[key]["count"] += 1
            inventory[key]["dates"].append(r["date"])

    # Group by category
    categories = {}
    for key, info in inventory.items():
        cat = info["equipment"].category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(info)

    cat_labels = {
        'smartphone': 'SMARTPHONES',
        'tablette': 'TABLETTES',
        'uc': 'UC FIXES',
        'tout_en_un': 'TOUT-EN-UN',
        'portable': 'PORTABLES',
        'imprimante': 'IMPRIMANTES',
        'reseau': 'EQUIPEMENT RESEAU',
        'peripherique': 'PERIPHERIQUES',
        'logiciel': 'LOGICIEL',
    }

    for cat, items in sorted(categories.items()):
        print(f"\n  {cat_labels.get(cat, cat)}")
        print(f"  {'-' * 40}")
        for info in items:
            eq = info["equipment"]
            print(f"    {eq.display_name}")
            if eq.serial:
                print(f"      SN: {eq.serial}")
            print(f"      Vu {info['count']}x")


if __name__ == "__main__":
    main()
