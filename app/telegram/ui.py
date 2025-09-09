from typing import List, Tuple

PAGE_SIZE = 6  # categories per page

def paginate_categories(categories: List[str], page: int = 0) -> Tuple[List[str], bool]:
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    slice_ = categories[start:end]
    has_more = end < len(categories)
    return slice_, has_more

def build_categories_keyboard(categories: List[str], page: int = 0) -> dict:
    """
    Inline keyboard with up to 6 categories per page; adds More/Back controls.
    Callback data:
      - CAT:<name>:PAGE:<n>
      - CATNAV:BACK:<n> / CATNAV:MORE:<n>
    """
    shown, has_more = paginate_categories(categories, page)

    # 🔒 Hide admin actions from end-user menu
    filtered: List[str] = []
    for c in shown:
        name = (c or "").strip().lower()
        if name in ("add service", "cancel service"):
            continue
        filtered.append(c)

    rows = [[{"text": c, "callback_data": f"CAT:{c}:PAGE:{page}"}] for c in filtered]

    nav = []
    if page > 0:
        nav.append({"text": "« Back", "callback_data": f"CATNAV:BACK:{page-1}"})
    if has_more:
        nav.append({"text": "More…", "callback_data": f"CATNAV:MORE:{page+1}"})
    if nav:
        rows.append(nav)
    return {"inline_keyboard": rows}
