# A parsed datasheet and a PDF response header do not establish schematic connectivity

On 2026-10-29 the carrier packaging investigation needed the actual LTC4359 Rev F Figure 10 before transcribing its floating-reference network. The web reader returned component labels and prose, but no usable diagram image. That text did not establish junctions or diode polarity. Earlier architecture review had checked primary text, not visual connectivity.

## Dated evidence

At approximately 15:55–15:58 UTC, direct `curl --http1.1 -L --max-time 45` of the public [manufacturer PDF](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc4359.pdf) timed out with zero bytes. A normal Chrome navigation returned HTTP 200 and `application/pdf`, yet Playwright's `response.body()` contained only 536 bytes beginning `<!doctype html>`: the browser PDF viewer wrapper, not the document.

An ordinary same-origin browser fetch after loading the public [product page](https://www.analog.com/en/products/ltc4359.html) returned HTTP 200 and **1,186,559 bytes beginning `%PDF-1.7`**. No credentials, account changes, challenge bypass or privileged endpoint were used. The successful operation was:

```javascript
await page.goto('https://www.analog.com/en/products/ltc4359.html');
// Run inside page.evaluate; return the bytes using the automation's binary transport.
const response = await fetch('/media/en/technical-documentation/data-sheets/ltc4359.pdf');
const bytes = new Uint8Array(await response.arrayBuffer());
```

`pdfinfo` identified “LTC4359 (Rev. F)”, Analog Devices, 20 pages, December 2021. PDF SHA256: `8d05e6ba4259028463bbdb751d639715506ef28d1bd5eabac1b012786ea7d970`. Rendering with `pdftoppm -f 12 -singlefile -scale-to 2200 -png` produced the inspected printed page 12, SHA256 `683206d5c5b09213ccc7f3fe9fae98451c4bf61529a8072adb92355c6dc7a5f7`. Root and the electrical author separately viewed this image before recording the source circuit's net map. The manufacturer's PDF and rendered image remain in the private source cache; public project records retain identities and derived facts rather than republishing the document.

## Cause and corrective rule

The exact cause of the command-line timeout was not established. Independently, Chrome's PDF viewer can return an HTML wrapper through navigation APIs despite a PDF content type. Neither a successful status/header nor flattened extraction proves that source pixels have been inspected.

For a schematic transcription, obtain the actual source bytes, verify the magic, revision and page identity, render the relevant page, and inspect every junction, polarity, pin and reference net. Bind the source hash and separate manufacturer designators from project designators. In particular, a floating VSS must not become global GND merely because both appear near the bottom of an extracted page. Keep the topology unresolved if the image cannot be obtained. A public browser fetch is a fallback for a download failure, not permission to bypass an access restriction.

## Limits

This verifies the identity and readability of one manufacturer's reference diagram. It does not qualify the circuit for Gyropup's supply, startup, charged-output, transient, thermal or packaging conditions. Native circuit changes still require exported-netlist checks, all-severity ERC, meaningful corruption controls and independent review. The retrieval method is not guaranteed for other sites or revisions. [Issue96](https://github.com/Valpatel/gyropup/issues/96) and [PR97](https://github.com/Valpatel/gyropup/pull/97) carry the finding with the related packaging work.
