import heapq
from collections import Counter
from typing import Any, Dict, List, Tuple

Color = Tuple[int, int, int]
RLE = Tuple[
    Color, int
]  # (color, pixel_length) - pixel_length could be 1 if original runs measured by run count


class Block:
    def __init__(self, start_idx: int, end_idx: int, color_counter: Dict[Color, int], total_measure: int):
        self.start = start_idx  # index into rle list (inclusive)
        self.end = end_idx  # inclusive
        self.counter = color_counter  # Counter: color -> count (measure: pixels or runs)
        self.total = total_measure
        # inherited = max count (most common color in this block)
        self.inherited = max(color_counter.values()) if color_counter else 0
        # neighbors will be set externally
        self.left = None
        self.right = None
        self.alive = True  # mark merged blocks as dead


def build_initial_blocks(rle: List[RLE], block_measure_target: int = 5000) -> List[Block]:
    """
    Group sequential rle items into initial blocks, each ~ block_measure_target measure (pixels or runs).
    """
    blocks = []
    n = len(rle)
    i = 0
    while i < n:
        cur_total = 0
        counter = Counter()
        start = i
        while i < n and (cur_total < block_measure_target or start == i):
            counter[rle[i][0]] += 1
            cur_total += 1
            i += 1
        end = i - 1
        blocks.append(Block(start, end, dict(counter), cur_total))
    # link neighbors
    for idx, b in enumerate(blocks):
        if idx > 0:
            b.left = blocks[idx - 1]
        if idx < len(blocks) - 1:
            b.right = blocks[idx + 1]
    return blocks


def merge_blocks(left: Block, right: Block) -> Block:
    """
    Merge two adjacent alive blocks and return the new block (not linked into neighbors).
    """
    new_counter = Counter(left.counter)
    new_counter.update(right.counter)
    new_total = left.total + right.total
    new_block = Block(left.start, right.end, dict(new_counter), new_total)
    return new_block


def compute_merge_gain(left: Block, right: Block) -> int:
    """
    gain = inherited_after_merge - (inherited_left + inherited_right)
    inherited computed as max count in counter
    """
    # inherited after merge
    merged_counter = Counter(left.counter)
    merged_counter.update(right.counter)
    inherited_merged = max(merged_counter.values()) if merged_counter else 0
    gain = inherited_merged - (left.inherited + right.inherited)
    return gain


def agglomerative_merge(rle: List[RLE], block_measure_target=5000, max_blocks=None):
    """
    Main greedy merging driver.
    Returns list of final blocks (in order).
    """
    blocks = build_initial_blocks(rle, block_measure_target=block_measure_target)
    if not blocks:
        return []

    # priority queue of merges: (-gain, merge_id, left_block)
    heap = []
    merge_id = 0

    # helper to push candidate merge if both alive
    def push_candidate(left: Block, right: Block):
        nonlocal merge_id
        if left is None or right is None or not left.alive or not right.alive:
            return
        g = compute_merge_gain(left, right)
        # only push if gain >= 0? For flexibility we push all, but we'll pop best positive gains first
        heapq.heappush(heap, (-g, merge_id, left, right))
        merge_id += 1

    # push all initial neighbors
    for b in blocks:
        if b.right:
            push_candidate(b, b.right)

    # active set: keep track of blocks in a linked list via left/right attributes
    current_blocks_count = len(blocks)
    while heap:
        neg_gain, _, left, right = heapq.heappop(heap)
        gain = -neg_gain
        # ensure still valid neighbors and alive
        if (not left.alive) or (not right.alive) or left.right is not right:
            continue
        # stop if gain <= 0 and we are not forced to reduce blocks further
        if gain <= 0 and (max_blocks is None or current_blocks_count <= (max_blocks)):
            break
        # perform merge
        newb = merge_blocks(left, right)
        # attach neighbors
        L = left.left
        R = right.right
        newb.left = L
        newb.right = R
        if L:
            L.right = newb
        if R:
            R.left = newb
        # mark old as dead
        left.alive = False
        right.alive = False
        newb.alive = True
        # push new candidates (L,newb) and (newb,R)
        push_candidate(L, newb)
        push_candidate(newb, R)
        current_blocks_count -= 1
        # If reached desired block count, we can stop after cleanup
        if max_blocks is not None and current_blocks_count <= max_blocks:
            break

    # collect alive blocks in order
    # find leftmost
    node = None
    for b in blocks:
        if b.alive and b.left is None:
            node = b
            break
    # if none found (because leftmost merged), find any alive and walk leftwards
    if node is None:
        # find any alive and go left until left is None
        for b in blocks:
            if b.alive:
                node = b
                while node.left:
                    node = node.left
                break
    # traverse
    final = []
    while node:
        final.append(node)
        node = node.right
    return final
