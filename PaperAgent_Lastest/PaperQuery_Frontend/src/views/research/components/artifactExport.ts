// Local, dependency-free DOCX export. Research content never leaves the browser.
const escapeXML = (value: string) => value.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]!)).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '')
export const escapeHTML = escapeXML

function runs(node: Node, bold = false, italic = false): string {
  if (node.nodeType === Node.TEXT_NODE) return (node.textContent || '').split('\n').map((text, i) => `${i ? '<w:r><w:br/></w:r>' : ''}<w:r>${bold || italic ? `<w:rPr>${bold ? '<w:b/>' : ''}${italic ? '<w:i/>' : ''}</w:rPr>` : ''}<w:t xml:space="preserve">${escapeXML(text)}</w:t></w:r>`).join('')
  if (!(node instanceof Element)) return ''
  if (node.tagName === 'BR') return '<w:r><w:br/></w:r>'
  const result = Array.from(node.childNodes).map(child => runs(child, bold || ['B', 'STRONG', 'TH'].includes(node.tagName), italic || ['I', 'EM'].includes(node.tagName))).join('')
  if (node.tagName === 'A') {
    const url = node.getAttribute('href') || ''
    if (/^https?:\/\//i.test(url) && node.textContent !== url) return result + runs(document.createTextNode(` (${url})`))
  }
  return result
}

const paragraph = (content: string, style = '', prefix = '') => `<w:p>${style ? `<w:pPr><w:pStyle w:val="${style}"/></w:pPr>` : ''}${prefix ? runs(document.createTextNode(prefix)) : ''}${content}</w:p>`
function blocks(parent: Element): string {
  return Array.from(parent.childNodes).map(node => {
    if (!(node instanceof Element)) return node.textContent?.trim() ? paragraph(runs(node)) : ''
    const tag = node.tagName
    if (tag === 'TABLE') {
      const rows = Array.from(node.querySelectorAll('tr'))
      const count = Math.max(1, ...rows.map(r => r.cells.length))
      const width = Math.floor(9360 / count)
      return `<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/><w:tblLayout w:type="fixed"/><w:tblBorders>${['top','left','bottom','right','insideH','insideV'].map(side => `<w:${side} w:val="single" w:sz="4" w:color="D8D0C6"/>`).join('')}</w:tblBorders></w:tblPr><w:tblGrid>${Array(count).fill(`<w:gridCol w:w="${width}"/>`).join('')}</w:tblGrid>${rows.map(row => `<w:tr>${row.querySelector('th') ? '<w:trPr><w:tblHeader/></w:trPr>' : ''}${Array.from(row.cells).map(cell => `<w:tc><w:tcPr><w:tcW w:w="${width}" w:type="dxa"/>${cell.tagName === 'TH' ? '<w:shd w:fill="F1EDE6"/>' : ''}</w:tcPr>${paragraph(runs(cell))}</w:tc>`).join('')}</w:tr>`).join('')}</w:tbl>`
    }
    if (tag === 'UL' || tag === 'OL') return Array.from(node.children).map((li, index) => {
      const text = li.cloneNode(true) as Element
      text.querySelectorAll('ul,ol').forEach(list => list.remove())
      return paragraph(runs(text), '', tag === 'OL' ? `${index + 1}. ` : '• ') + Array.from(li.children).filter(el => ['UL', 'OL'].includes(el.tagName)).map(el => blocks(el.parentElement === li ? wrap(el) : el)).join('')
    }).join('')
    if (/^H[1-6]$/.test(tag)) return paragraph(runs(node), `Heading${Math.min(3, Number(tag[1]))}`)
    if (tag === 'PRE') return paragraph(runs(node), 'Code')
    if (tag === 'HR') return paragraph(runs(document.createTextNode('────────────────────────')))
    if (['DIV', 'SECTION', 'ARTICLE', 'BLOCKQUOTE'].includes(tag)) return blocks(node)
    return paragraph(runs(node))
  }).join('')
}
function wrap(el: Element) { const div = document.createElement('div'); div.append(el.cloneNode(true)); return div }

// ZIP store entries (UTF-8 names, CRC32). OOXML does not require compression.
function zip(files: Record<string, string>): Uint8Array {
  const encoder = new TextEncoder(), chunks: Uint8Array[] = [], directory: Uint8Array[] = []
  let offset = 0
  const crc = (bytes: Uint8Array) => { let n = 0xffffffff; for (const b of bytes) { n ^= b; for (let i=0;i<8;i++) n = (n >>> 1) ^ ((n & 1) ? 0xedb88320 : 0) } return (n ^ 0xffffffff) >>> 0 }
  const header = (length: number) => { const bytes = new Uint8Array(length); return { bytes, view: new DataView(bytes.buffer) } }
  for (const [path, text] of Object.entries(files)) {
    const name = encoder.encode(path), body = encoder.encode(text), checksum = crc(body)
    const local = header(30 + name.length), central = header(46 + name.length)
    local.view.setUint32(0, 0x04034b50, true); local.view.setUint16(4, 20, true); local.view.setUint16(6, 0x800, true)
    local.view.setUint32(14, checksum, true); local.view.setUint32(18, body.length, true); local.view.setUint32(22, body.length, true); local.view.setUint16(26, name.length, true); local.bytes.set(name, 30)
    central.view.setUint32(0, 0x02014b50, true); central.view.setUint16(4, 20, true); central.view.setUint16(6, 20, true); central.view.setUint16(8, 0x800, true)
    central.view.setUint32(16, checksum, true); central.view.setUint32(20, body.length, true); central.view.setUint32(24, body.length, true); central.view.setUint16(28, name.length, true); central.view.setUint32(42, offset, true); central.bytes.set(name, 46)
    chunks.push(local.bytes, body); directory.push(central.bytes); offset += local.bytes.length + body.length
  }
  const end = header(22), size = directory.reduce((n, c) => n+c.length, 0)
  end.view.setUint32(0, 0x06054b50, true); end.view.setUint16(8, directory.length, true); end.view.setUint16(10, directory.length, true); end.view.setUint32(12, size, true); end.view.setUint32(16, offset, true)
  const result = new Uint8Array(offset + size + 22); let index = 0
  for (const chunk of [...chunks, ...directory, end.bytes]) { result.set(chunk, index); index += chunk.length }
  return result
}

export function exportArtifactWord(title: string, html: string) {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  const declaration = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
  const styles = `<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Microsoft YaHei"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="320" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>${[1,2,3].map(n=>`<w:style w:type="paragraph" w:styleId="Heading${n}"><w:name w:val="heading ${n}"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="${n-1}"/></w:pPr><w:rPr><w:b/><w:sz w:val="${[32,28,25][n-1]}"/></w:rPr></w:style>`).join('')}<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="19"/></w:rPr></w:style></w:styles>`
  const files = {
    '[Content_Types].xml': declaration + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>',
    '_rels/.rels': declaration + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
    'word/document.xml': declaration + `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${blocks(doc.body)}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1273" w:right="1273" w:bottom="1273" w:left="1273"/></w:sectPr></w:body></w:document>`,
    'word/styles.xml': declaration + styles,
    'word/_rels/document.xml.rels': declaration + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
  }
  const blob = new Blob([zip(files)], {type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'})
  const url = URL.createObjectURL(blob), link = document.createElement('a')
  link.href = url; link.download = (title.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_').replace(/[. ]+$/g, '').slice(0, 100) || '研究结果') + '.docx'
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000)
}

export async function copyArtifact(html: string, text: string) {
  if (navigator.clipboard?.write && typeof ClipboardItem !== 'undefined') {
    try { await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([html],{type:'text/html'}),'text/plain':new Blob([text],{type:'text/plain'})})]); return } catch { /* Plain text fallback for restricted browsers. */ }
  }
  if (navigator.clipboard?.writeText) { try { await navigator.clipboard.writeText(text); return } catch { /* Legacy fallback. */ } }
  const previous = document.activeElement as HTMLElement | null, field = document.createElement('textarea')
  field.value = text; field.style.cssText = 'position:fixed;left:-9999px;top:0'; document.body.append(field); field.select()
  try { if (!document.execCommand('copy')) throw new Error('Clipboard unavailable') } finally { field.remove(); previous?.focus() }
}
