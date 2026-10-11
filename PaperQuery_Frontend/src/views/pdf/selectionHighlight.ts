export interface SelectionMark { page: number; x: number; y: number; width: number; height: number }

// Browser fallback fonts can have different advance widths from the PDF font.
// Fit the invisible horizontal selection spans to the PDF's own text metrics.
export function calibrateTextLayer(payload: { textDivs: HTMLElement[]; textContent?: { items: unknown[] } }) {
  const items = (payload.textContent?.items || []).filter((item): item is {str: string; width: number} => !!item && typeof item === 'object' && 'str' in item)
  if (items.length !== payload.textDivs.length) return
  payload.textDivs.forEach((span, index) => {
    const item = items[index]
    if (span.textContent !== item.str || !item.width) return
    const style = getComputedStyle(span), scale = Number(style.getPropertyValue('--scale-factor'))
    if (!scale) return
    const matrix = new DOMMatrix(style.transform === 'none' ? undefined : style.transform)
    // Rotated/vertical text keeps PDF.js's native transform.
    if (Math.abs(matrix.b) > .001 || Math.abs(matrix.c) > .001) return
    const actualWidth = span.getBoundingClientRect().width, targetWidth = item.width * scale
    if (actualWidth > 0 && targetWidth > 0 && Math.abs(actualWidth-targetWidth) > .5) {
      matrix.a *= targetWidth / actualWidth
      span.style.transform = matrix.toString()
    }
  })
}

// Measure selected leaf text, never the full multi-line DOM Range bounding box.
// Coordinates are normalized to page width so marks follow zoom and split-pane resize.
export function selectionMarks(selection: Selection, container: HTMLElement): SelectionMark[] {
  const marks: SelectionMark[] = []
  for (let i = 0; i < selection.rangeCount; i++) {
    const selected = selection.getRangeAt(i)
    if (selected.collapsed || !container.contains(selected.startContainer) || !container.contains(selected.endContainer)) continue
    for (const layer of container.querySelectorAll<HTMLElement>('.textLayer')) {
      if (!selected.intersectsNode(layer)) continue
      const page = layer.closest<HTMLElement>('[data-pdf-page]')
      if (!page) continue
      const pageBox = page.getBoundingClientRect(), layerBox = layer.getBoundingClientRect()
      if (!pageBox.width) continue
      const walker = document.createTreeWalker(layer, NodeFilter.SHOW_TEXT)
      let node: Node | null
      while ((node = walker.nextNode())) {
        if (!node.textContent?.trim() || !selected.intersectsNode(node)) continue
        const span = node.parentElement
        if (!span || span.closest('.endOfContent')) continue
        const range = document.createRange()
        range.selectNodeContents(node)
        if (selected.startContainer === node) range.setStart(node, selected.startOffset)
        if (selected.endContainer === node) range.setEnd(node, selected.endOffset)
        if (range.collapsed) continue
        const spanBox = span.getBoundingClientRect()
        for (const rect of range.getClientRects()) {
          const left = Math.max(rect.left, spanBox.left, layerBox.left)
          const right = Math.min(rect.right, spanBox.right, layerBox.right)
          const top = Math.max(rect.top, spanBox.top, layerBox.top)
          const bottom = Math.min(rect.bottom, spanBox.bottom, layerBox.bottom)
          if (right-left < .5 || bottom-top < .5) continue
          const mark = {page:Number(page.dataset.pdfPage),x:(left-pageBox.left)/pageBox.width,y:(top-pageBox.top)/pageBox.width,width:(right-left)/pageBox.width,height:(bottom-top)/pageBox.width}
          if (!marks.some(m => m.page === mark.page && Math.abs(m.x-mark.x)<.0001 && Math.abs(m.y-mark.y)<.0001 && Math.abs(m.width-mark.width)<.0001)) marks.push(mark)
        }
      }
    }
  }
  return marks
}
