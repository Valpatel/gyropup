// A missing optional export is different from a failed or malformed response.
// The fetch function is injectable so static Markdown reads only its published bundle.
export function createDataReader(fetcher = globalThis.fetch) {
  async function read(url, type, { optional = false, label = String(url), validate, timeout = 20000 } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      let response;
      try { response = await fetcher(url, { cache: 'no-store', signal: controller.signal }); }
      catch (cause) { throw new Error(`${label}: ${controller.signal.aborted ? 'the request timed out' : 'the connection failed'}. Please retry.`, { cause }); }
      if (optional && response.status === 404) { await response.body?.cancel(); return null; }
      if (!response.ok) { await response.body?.cancel(); throw new Error(`${label}: the server returned HTTP ${response.status}. Please retry.`); }
      let value;
      try { value = await response[type](); }
      catch (cause) { throw new Error(`${label}: ${controller.signal.aborted ? 'the request timed out' : 'the downloaded data could not be read'}. Please retry.`, { cause }); }
      if (type === 'json' && (!value || typeof value !== 'object')) throw new Error(`${label}: the downloaded JSON has no usable data.`);
      if (validate && !validate(value)) throw new Error(`${label}: the downloaded data has an unexpected format.`);
      return value;
    } finally { clearTimeout(timer); }
  }
  return {
    json: (url, options) => read(url, 'json', options),
    text: (url, options) => read(url, 'text', options),
    bytes: (url, options) => read(url, 'arrayBuffer', options),
  };
}

export const isRecord = value => !!value && typeof value === 'object' && !Array.isArray(value);
export const isMarkdown = value => typeof value === 'string' && value.trim().length>0 && !/^\s*(?:<!doctype\s+html|<html\b)/i.test(value);

/** Reject empty/HTML responses before STLLoader can mistake them for binary STL. */
export function validateSTLBytes(bytes) {
  if (!(bytes instanceof ArrayBuffer) || bytes.byteLength < 84) throw new Error('The downloaded part is empty or is not STL geometry.');
  const data=new Uint8Array(bytes),solid=[115,111,108,105,100];
  const binary = 84 + new DataView(bytes).getUint32(80, true) * 50 === bytes.byteLength;
  // Match the vendored STLLoader's byte-level classifier: trimming whitespace or
  // accepting uppercase SOLID could admit text it treats as a huge binary mesh.
  const ascii=[0,1,2,3,4].some(offset=>solid.every((value,index)=>data[offset+index]===value));
  if (!binary && !ascii) throw new Error('The downloaded part is not STL geometry.');
}

export function validateGeometry(geometry) {
  const p = geometry?.attributes?.position;
  if (!p || p.count < 3 || p.count % 3 || !p.array.every(Number.isFinite)) throw new Error('The downloaded part has no valid triangles.');
  geometry.computeBoundingBox();
  const b = geometry.boundingBox;
  if (b.isEmpty() || b.min.distanceToSquared(b.max) === 0) throw new Error('The downloaded part has empty geometry.');
  return geometry;
}
