# DNS filter warnings need evidence from the failing path

On 2026-10-30 a visitor reported an untrusted certificate for `www.gyropup.com`,
then a DNS-firewall message saying a name server was on a blocklist. Public
OpenSSL, curl and a fresh Chrome instance verified both hostnames successfully.
Both Cloudflare Pages domains and their validation were active; five recursive
resolvers and the authoritative DNS agreed. Commands, certificate fingerprints,
limits and domain-age evidence are in the
[dated receipt](../../docs/validation/public-https.md) and
[issue 119](https://github.com/Valpatel/gyropup/issues/119).

The leading explanation is a DNS-security block with a substituted HTTPS block
page. The exact vendor, rule and served certificate on the affected network
remain unknown; a healthy public probe cannot prove that explanation or resolve
the visitor's failure. Name-server reputation rules can affect unrelated sites
on shared DNS infrastructure. Newly registered status is another possible policy
input, not a diagnosed cause.

Collect the actual filter event and certificate before changing hosting. Separate
hostname/chain/expiry errors, DNS policy, HTTPS interception and HTTP-level bot
blocking. Refresh existing Wrangler OAuth before calling authentication blocked;
a successful Pages read with a zone-settings 403 does not grant settings access.
Keep normal TLS verification enabled. Do not send a policy or reputation review on the owner's behalf without
authorization; here the owner chose not to file one. Never label the issue fixed
from an unaffected network alone.

No hosting configuration changed during this investigation. The receipt records
the unaudited zone settings, local IPv6 limitation and completed independent
four-address www assessment.
These limits must accompany any subsequent recovery claim.
