# WW.CX NTP firewall comment-quoting incident — 2026-08-15

## Summary

During the first attended run of the approved public NTP firewall publication helper, the persistent nftables edit was syntax-checked successfully, but the targeted live insert failed with:

```text
Error: syntax error, unexpected colon, expecting end of file or newline or semicolon
insert rule inet wwcxfw input position 12 ip daddr 89.147.109.253 udp dport 123 accept comment wwcx:public-ntp-v4
```

The helper then reported that current-run changes were rolled back. This was the intended safe failure behavior: public UDP/123 was not accepted by the live firewall and the persistent file was restored.

## Root cause

The live rule was constructed as ordinary shell arguments ending with:

```sh
comment "$RULE_COMMENT"
```

Shell quote removal meant nft received the comment value as the token `wwcx:public-ntp-v4`, without literal nft-language quotes. The colon was therefore parsed as syntax rather than as part of a string.

## Correction

The live insert is now rendered as nft language in the deployment evidence directory and passed through `nft -c -f` followed by `nft -f`. The rendered rule preserves literal double quotes around the comment string:

```text
comment "wwcx:public-ntp-v4"
```

This keeps the existing targeted insertion strategy, including placement immediately before the reviewed `wwcx:public-web` rule. It still does not reload or flush the full ruleset, so runtime Big Bird controls remain intact.

## Acceptance boundary

This correction changes only the deployment helper and validation/documentation. The live firewall must be retried on Edge1 and verified independently before public NTP reachability is accepted.
