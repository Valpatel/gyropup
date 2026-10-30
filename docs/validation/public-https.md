# Public HTTPS and corporate DNS filtering

Investigation: [issue 119](https://github.com/Valpatel/gyropup/issues/119).
Checks below were made on **2026-10-30, 06:57–07:06 UTC**. The reported corporate
network failure remains unresolved; successful public probes do not establish
that the affected visitor reaches the same server.

The visitor reported an operating-system certificate-trust warning for
`www.gyropup.com`, followed by a DNS-firewall message saying that a name server
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
does not test the remote service. A separate SSL Labs assessment of www is
tracked in issue 119; at 07:06 UTC its first IPv6 endpoint had completed with
grade A and no warnings, while the other endpoints were still being assessed.
Do not treat a partial external assessment as coverage of every address.

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

## Review request, ready for the identified policy owner

The text below is a draft, **not sent**. The owner should attach the actual block
event, timestamp, vendor and category before submitting it through the company's
approved review process. Do not publish internal network or employee details.

> Please review the DNS-security block affecting `gyropup.com` and
> `www.gyropup.com`. The site is a public robotics project with design documents
> and browser simulations, hosted on Cloudflare Pages. A visitor sees a message
> that a name server is listed on a blocklist, together with an HTTPS trust
> warning. Please identify the matched indicator, feed, policy and action:
> queried hostname, answer IP, name-server hostname or name-server IP.
>
> Public checks on 2026-10-30 verified both hostnames' Google Trust Services
> certificates, HTTPS 200 responses and active Pages custom-domain validation.
> The authoritative nameservers are `aspen.ns.cloudflare.com` and
> `everton.ns.cloudflare.com`. Please check for a stale or overly broad shared
> nameserver classification. If this is a reputation error, please request a
> vendor correction; if it is an intentional policy, please review whether a
> narrow exception for these two hostnames is appropriate. Please retain normal
> TLS validation and other protections. Evidence and certificate fingerprints:
> https://github.com/Valpatel/gyropup/blob/ops/https-diagnostics/docs/validation/public-https.md

Official references support the diagnostic distinction, but do not identify this
visitor's vendor:

- [Infoblox RPZ documentation](https://www.infoblox.com/dns-security-resource-center/dns-security-solutions/dns-security-solutions-response-policy-zones-rpz/)
  describes name-server triggers that can affect every domain served by that
  server and redirection to internal security pages.
- [Cisco's HTTPS block-page explanation](https://community.cisco.com/t5/umbrella-announcements/umbrella-dns-block-pages-and-certificate-trust-on-unmanaged/ta-p/5314311)
  explains why a substituted block page can produce a browser trust warning.
- If the identified vendor is Infoblox, use its
  [Dossier feedback process](https://docs.infoblox.com/space/BloxOneThreatDefense/230493737/Dossier%2BThreat%2BResearch%2BFeedback)
  for an incorrect threat indicator or category. If it is Zscaler, its
  [Site Review process](https://help.zscaler.com/zia/looking-up-urls-site-review)
  supports category review; a DNS threat/feed decision may instead require the
  administrator's support case with the actual DNS event.
- [Cloudflare Pages custom-domain guidance](https://developers.cloudflare.com/pages/configuration/custom-domains/)
  requires the registered domain and correct DNS. Both are present here.

Changing CAs, disabling HTTPS or moving nameservers has no demonstrated basis
in this evidence. Keep issue 119 open until the affected path is identified and
verified after the policy correction, or the policy owner confirms an intentional
restriction.
