# Public HTTPS and corporate DNS filtering

Investigation: [issue 119](https://github.com/Valpatel/gyropup/issues/119).
Checks below were made on **2026-10-30, 06:57–07:11 UTC**. The reported corporate
network failure remains unresolved; successful public probes do not establish
that the affected visitor reaches the same server.

The visitor reported an operating-system certificate-trust warning for
`www.gyropup.com` with code `NET::ERR_CERT_AUTHORITY_INVALID`, followed by a DNS-firewall message saying that a name server
was on a blocklist. This establishes a filtering symptom. A substituted HTTPS
block page could explain the certificate warning, but the affected device's
certificate, DNS answer and filter event have not yet been captured. The filter
vendor, exact rule and any reputation classification are unknown.

## Verified public path

| Check | Observed result |
| --- | --- |
| Cloudflare zone | Active, full, not paused |
| Apex and www DNS | Proxied CNAMEs to `gyropup.pages.dev`; no competing A/AAAA records in the zone |
| Pages custom domains | Both names active; verification and HTTP validation active; Google CA |
| Recursive DNS | Cloudflare, Google, Quad9, Cloudflare malware and family resolvers agree on A/AAAA for both names |
| Authoritative DNS | `aspen.ns.cloudflare.com`, `everton.ns.cloudflare.com`; direct answers agree with recursive DNS |
| Public IPv4 | `104.21.30.46`, `172.67.150.142` |
| Public IPv6 | `2606:4700:3030::6815:1e2e`, `2606:4700:3030::ac43:968e` |
| HTTP | Both names redirect 301 to HTTPS on the same hostname |
| HTTPS over IPv4 | Both names at both addresses return 200 with normal certificate verification |
| TLS versions | OpenSSL verifies hostname and chain on both IPv4 addresses using TLS 1.2 and TLS 1.3 |
| Fresh browser | Installed Chrome 151.0.7922.71 loads both origins with HTTP 200 and `isSecureContext === true`; no certificate override or DNS mapping |
| CAA / DNSSEC | No CAA restriction; no parent DS; zone DNSSEC disabled, so no stale DS mismatch observed |
| Registration | Verisign RDAP records creation at `2026-10-28T14:41:31Z`; this does not establish the filter's reason |

Each endpoint sends the hostname's leaf certificate, the Google Trust Services
WE1 intermediate, and GTS Root R4 cross-signed by GlobalSign Root CA. OpenSSL's
normal trust path verifies to the installed GTS Root R4. A separate attempted
test using only an old GlobalSign root could not run because that root file is
absent locally; no legacy trust-store coverage is claimed.

| Certificate | Validity (UTC) | SHA-256 fingerprint |
| --- | --- | --- |
| `gyropup.com` (same sole SAN) | 2026-10-28 14:50:48 to 2027-01-26 15:50:46 | `051f6dc626618ebfd1488ea4e2885a29a683a263a9ffc9d697547a4b544a029c` |
| `www.gyropup.com` (same sole SAN) | 2026-10-28 23:05:54 to 2027-01-27 00:05:52 | `2cec00dd9ace878493d0b71f27f482a35a4216c290238f2b204c665346e94cd0` |

The workstation has no IPv6 default route. Its immediate IPv6 connection failure
does not test the remote service. An independent SSL Labs assessment completed
at the 07:11 UTC retrieval: **all four www addresses (two IPv4, two IPv6) were
Ready, grade A, with no warnings**. The [machine-readable summary](public-https-ssllabs.json)
records the source API, retrieval time and individual endpoint results. This
external assessment covers www; it does not reproduce the corporate policy path.

Normal `npx wrangler whoami` succeeded as the existing OS user using the installed
Node 22 runtime. Pages reads work with that refreshed OAuth credential. Both the
DNS-specific token and refreshed OAuth receive 403 / 9109 from the zone's
Universal SSL, certificate-pack and SSL/settings endpoints. These settings
therefore remain **unread**, not proven misconfigured. No credential expansion
was requested. The public chain and Pages status are independently observed.

**Live changes and rollback:** none. DNS, proxy, TLS settings and certificates
were unchanged; there is nothing to roll back. No deployment was necessary.
The HTTP 403 / Cloudflare 1010 response to default Python clients in
[issue 107](https://github.com/Valpatel/gyropup/issues/107) remains a separate
application-request filtering investigation.

## Reproduce without weakening certificate checks

```sh
date -u
dig @1.1.1.1 www.gyropup.com A +noall +answer
dig @1.1.1.1 www.gyropup.com AAAA +noall +answer
dig @8.8.8.8 www.gyropup.com A +noall +answer
dig @9.9.9.9 www.gyropup.com AAAA +noall +answer
dig @aspen.ns.cloudflare.com gyropup.com NS +noall +answer
curl -I https://www.gyropup.com/
openssl s_client -connect www.gyropup.com:443 \
  -servername www.gyropup.com -verify_hostname www.gyropup.com \
  -verify_return_error -showcerts </dev/null
```

Repeat for the apex. A diagnostic `curl --resolve` against an independently
observed public address preserves certificate checks, but record the override
and do not represent it as the affected corporate resolver's behavior. On the
affected network, an administrator should capture the ordinary resolver answer,
browser certificate issuer/fingerprint and matching DNS-security event. Do not
change the employee's resolver or bypass the browser warning to collect evidence.

## Could the domain simply be too new?

Yes, this is plausible. [Verisign's registry RDAP record](https://rdap.verisign.com/com/v1/domain/GYROPUP.COM)
records registration at **2026-10-28 14:41:31 UTC**, about 40 hours before the
initial probes above. Registration age and a filter's first observation are
different clocks. For example,
[Cisco Umbrella's newly seen category](https://www.cisco.com/c/en/us/support/docs/security/umbrella/224735-enable-newly-seen-domains-security.html)
uses a 24-hour observation window, while
[Palo Alto's newly registered category](https://docs.paloaltonetworks.com/advanced-url-filtering/administration/url-filtering-basics/url-categories?otp=risk-categories)
covers registrations in the preceding 32 days. These examples establish that
such policies exist; neither identifies the affected network's product or rule.
There is no evidence-based date when this particular block will disappear.

The name-server wording leaves other explanations open.
[Infoblox's RPZ documentation](https://www.infoblox.com/dns-security-resource-center/dns-security-solutions/dns-security-solutions-response-policy-zones-rpz/)
describes name-server triggers that can affect every domain served by a shared
server. [Cisco's HTTPS block-page explanation](https://community.cisco.com/t5/umbrella-announcements/umbrella-dns-block-pages-and-certificate-trust-on-unmanaged/ta-p/5314311)
explains why a substituted block page can produce a browser trust warning.
These are documented mechanisms, not identification of this visitor's vendor.

No policy-review request will be filed, per the owner's decision. No external
message was sent. The public TLS investigation is complete; the corporate DNS
filter's classification and eventual recovery remain unverified. A later normal
visit can establish whether the block has cleared. If investigation is resumed,
start with the affected network's actual DNS answer, certificate and filter event.

Changing CAs, disabling HTTPS or moving nameservers has no demonstrated basis
in this evidence. Keep the corporate-policy observation separate from an actual
hosting defect, and do not claim that waiting is a guaranteed fix.
