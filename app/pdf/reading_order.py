from collections import defaultdict

from app.db.models import Block


def _is_two_column(blocks: list[Block]) -> bool:
    if len(blocks) < 6:
        return False
    centers = sorted((b.bbox[0] + b.bbox[2]) / 2 for b in blocks)
    gaps = [(centers[i + 1] - centers[i], i) for i in range(len(centers) - 1)]
    max_gap, index = max(gaps, default=(0, 0))
    spread = centers[-1] - centers[0] if centers else 0
    left_count = index + 1
    right_count = len(centers) - left_count
    return spread > 0 and max_gap / spread > 0.22 and left_count >= 2 and right_count >= 2


def resolve_page_orders(blocks: list[Block]) -> list[tuple[int, int, bool]]:
    by_page: dict[int, list[Block]] = defaultdict(list)
    for block in blocks:
        by_page[block.page_number].append(block)

    updates: list[tuple[int, int, bool]] = []
    for page_blocks in by_page.values():
        two_column = _is_two_column(page_blocks)
        if two_column:
            centers = sorted((b.bbox[0] + b.bbox[2]) / 2 for b in page_blocks)
            split_x = (centers[len(centers) // 2 - 1] + centers[len(centers) // 2]) / 2
            ordered = sorted(page_blocks, key=lambda b: (0 if (b.bbox[0] + b.bbox[2]) / 2 < split_x else 1, b.bbox[1], b.bbox[0]))
        else:
            ordered = sorted(page_blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
        for order, block in enumerate(ordered, start=1):
            updates.append((block.id, order, False))
    return updates
