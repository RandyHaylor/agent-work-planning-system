/**
 * Drag-to-reorder for any list of elements laid out in rows or in a grid, with mouse,
 * touch and pen alike (pointer events, so it works on phones where HTML drag-and-drop
 * does not).
 *
 * makeListReorderableByDragging(listElement, {itemSelector, handleSelector, onMove})
 *   - an item is dragged by its handle and follows the pointer;
 *   - the item nearest the pointer is marked as the drop target ("is-drop-target");
 *   - on release, onMove(fromIndex, toIndex) is called. The caller changes its data and
 *     re-renders; this module does not keep the moved order itself.
 * Keyboard: a focused handle moves its item with the arrow keys.
 */

export function makeListReorderableByDragging(listElement, { itemSelector, handleSelector, onMove }) {
  let drag = null;

  const items = () => [...listElement.querySelectorAll(itemSelector)];

  const indexOfItemNearest = (x, y) => {
    let nearestIndex = drag.fromIndex;
    let nearestDistance = Infinity;
    drag.itemRects.forEach((rect, index) => {
      const dx = x - (rect.left + rect.width / 2);
      const dy = y - (rect.top + rect.height / 2);
      const distance = dx * dx + dy * dy;
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestIndex = index;
      }
    });
    return nearestIndex;
  };

  listElement.addEventListener("pointerdown", (event) => {
    const handle = event.target.closest(handleSelector);
    if (!handle || !listElement.contains(handle) || event.button > 0) return;
    const item = handle.closest(itemSelector);
    const allItems = items();
    event.preventDefault();
    try {
      handle.setPointerCapture(event.pointerId);
    } catch {
      // no live pointer to capture (a synthetic event); moves still arrive on the list
    }
    drag = {
      item,
      pointerId: event.pointerId,
      fromIndex: allItems.indexOf(item),
      toIndex: allItems.indexOf(item),
      startX: event.clientX,
      startY: event.clientY,
      itemRects: allItems.map((element) => element.getBoundingClientRect()),
    };
    item.classList.add("is-being-dragged");
    listElement.classList.add("is-reordering");
  });

  listElement.addEventListener("pointermove", (event) => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    drag.item.style.transform =
      `translate(${event.clientX - drag.startX}px, ${event.clientY - drag.startY}px)`;
    drag.toIndex = indexOfItemNearest(event.clientX, event.clientY);
    items().forEach((element, index) => {
      element.classList.toggle("is-drop-target", index === drag.toIndex && index !== drag.fromIndex);
    });
  });

  const endDrag = (event) => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const { fromIndex, toIndex } = drag;
    items().forEach((element) => {
      element.style.transform = "";
      element.classList.remove("is-drop-target");
    });
    drag.item.classList.remove("is-being-dragged");
    listElement.classList.remove("is-reordering");
    drag = null;
    if (fromIndex !== toIndex) onMove(fromIndex, toIndex);
  };
  listElement.addEventListener("pointerup", endDrag);
  listElement.addEventListener("pointercancel", endDrag);

  listElement.addEventListener("keydown", (event) => {
    const handle = event.target.closest(handleSelector);
    const step = { ArrowUp: -1, ArrowLeft: -1, ArrowDown: 1, ArrowRight: 1 }[event.key];
    if (!handle || !step) return;
    const allItems = items();
    const fromIndex = allItems.indexOf(handle.closest(itemSelector));
    const toIndex = fromIndex + step;
    if (toIndex < 0 || toIndex >= allItems.length) return;
    event.preventDefault();
    onMove(fromIndex, toIndex);
    items()[toIndex]?.querySelector(handleSelector)?.focus();
  });
}
