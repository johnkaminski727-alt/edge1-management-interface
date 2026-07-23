#!/usr/bin/env bash
set -Eeuo pipefail

# Discover Bitcoin wallet installations and identify watch-only wallets without
# printing addresses, descriptors, extended keys, seeds, or private key data.
#
# Safe to run as an ordinary user. Root privileges improve filesystem and
# service visibility, but the script never changes configuration or wallet data.

export LC_ALL=C

have() { command -v "$1" >/dev/null 2>&1; }
section() { printf '\n== %s ==\n' "$1"; }
info() { printf '%s\n' "$*"; }

HOST_FQDN="$(hostname -f 2>/dev/null || hostname 2>/dev/null || printf unknown)"
CURRENT_USER="$(id -un 2>/dev/null || printf unknown)"

printf 'Bitcoin wallet discovery report\n'
printf 'host: %s\n' "$HOST_FQDN"
printf 'user: %s\n' "$CURRENT_USER"
printf 'time_utc: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'mode: read-only\n'

section "Processes"
if have pgrep; then
  for proc in bitcoind bitcoin-qt electrum electrs fulcrum sparrow; do
    if pgrep -x "$proc" >/dev/null 2>&1; then
      printf '%-16s running\n' "$proc"
    else
      printf '%-16s not detected\n' "$proc"
    fi
  done
else
  ps -eo comm= 2>/dev/null | grep -E '^(bitcoind|bitcoin-qt|electrum|electrs|fulcrum|sparrow)$' || true
fi

section "System services"
if have systemctl; then
  systemctl list-units --type=service --all --no-legend 2>/dev/null \
    | awk 'BEGIN{IGNORECASE=1} /bitcoin|electrum|electrs|fulcrum|sparrow/{print $1, $3, $4}' \
    | sed -n '1,80p' || true
else
  info "systemctl unavailable"
fi

section "Installed wallet software"
for bin in bitcoin-cli bitcoind bitcoin-qt electrum electrs fulcrum sparrow; do
  if have "$bin"; then
    path="$(command -v "$bin")"
    version="$($bin --version 2>/dev/null | head -n 1 || true)"
    printf '%-16s %s%s\n' "$bin" "$path" "${version:+ | $version}"
  fi
done

section "Candidate data directories"
# Report directory paths and wallet-looking child names only. Never read wallet
# database contents or configuration secrets.
roots=(
  "$HOME/.bitcoin"
  "$HOME/.electrum"
  "$HOME/.local/share/Sparrow"
  "/var/lib/bitcoind"
  "/var/lib/bitcoin"
  "/srv/bitcoin"
  "/opt/bitcoin"
)

# Add home-directory candidates visible to the current account.
for home in /home/* /root; do
  [[ -d "$home" ]] || continue
  roots+=("$home/.bitcoin" "$home/.electrum" "$home/.local/share/Sparrow")
done

seen=''
for root in "${roots[@]}"; do
  [[ -e "$root" ]] || continue
  case " $seen " in *" $root "*) continue ;; esac
  seen+=" $root"
  printf 'candidate: %s\n' "$root"
  if [[ -d "$root/wallets" ]]; then
    find "$root/wallets" -mindepth 1 -maxdepth 2 \
      \( -type d -o -name wallet.dat \) -printf '  wallet-entry: %p\n' 2>/dev/null \
      | sed -n '1,80p' || true
  fi
  if [[ -f "$root/wallet.dat" ]]; then
    printf '  wallet-entry: %s/wallet.dat\n' "$root"
  fi
done

section "Bitcoin Core RPC discovery"
if ! have bitcoin-cli; then
  info "bitcoin-cli unavailable; filesystem candidates above are the available evidence."
  exit 0
fi

# Try the default datadir and common system datadirs. Authentication is delegated
# to Bitcoin Core cookie/config handling. No credentials are printed.
datadirs=("" "$HOME/.bitcoin" "/var/lib/bitcoind" "/var/lib/bitcoin")
RPC_OK=0

for datadir in "${datadirs[@]}"; do
  args=()
  label="default"
  if [[ -n "$datadir" ]]; then
    [[ -d "$datadir" ]] || continue
    args+=("-datadir=$datadir")
    label="$datadir"
  fi

  chain_json="$(bitcoin-cli "${args[@]}" -rpcwait=0 getblockchaininfo 2>/dev/null || true)"
  [[ -n "$chain_json" ]] || continue
  RPC_OK=1

  chain="$(printf '%s' "$chain_json" | sed -n 's/.*"chain"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
  printf 'rpc: reachable (%s)%s\n' "$label" "${chain:+, chain=$chain}"

  wallets_json="$(bitcoin-cli "${args[@]}" listwallets 2>/dev/null || true)"
  walletdir_json="$(bitcoin-cli "${args[@]}" listwalletdir 2>/dev/null || true)"

  loaded_count="$(printf '%s' "$wallets_json" | grep -o '"[^"]*"' 2>/dev/null | wc -l | tr -d ' ')"
  available_count="$(printf '%s' "$walletdir_json" | grep -o '"name"[[:space:]]*:[[:space:]]*"' 2>/dev/null | wc -l | tr -d ' ')"
  printf '  loaded_wallets: %s\n' "${loaded_count:-0}"
  printf '  available_wallets: %s\n' "${available_count:-0}"

  # Extract loaded wallet names only long enough to query getwalletinfo. Names are
  # operational metadata; no addresses, descriptors, keys, or transactions appear.
  while IFS= read -r wallet; do
    [[ -n "$wallet" ]] || continue
    encoded="$(python3 - "$wallet" <<'PY' 2>/dev/null || printf '%s' "$wallet"
import sys, urllib.parse
print(urllib.parse.quote(sys.argv[1], safe=''))
PY
)"
    info_json="$(bitcoin-cli "${args[@]}" -rpcwallet="$encoded" getwalletinfo 2>/dev/null || true)"
    [[ -n "$info_json" ]] || {
      printf '  wallet: %s | status=loaded, details=unavailable\n' "$wallet"
      continue
    }

    private_keys="$(printf '%s' "$info_json" | sed -n 's/.*"private_keys_enabled"[[:space:]]*:[[:space:]]*\(true\|false\).*/\1/p' | head -n 1)"
    descriptors="$(printf '%s' "$info_json" | sed -n 's/.*"descriptors"[[:space:]]*:[[:space:]]*\(true\|false\).*/\1/p' | head -n 1)"
    txcount="$(printf '%s' "$info_json" | sed -n 's/.*"txcount"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' | head -n 1)"
    scanning="$(printf '%s' "$info_json" | grep -q '"scanning"[[:space:]]*:[[:space:]]*false' && printf no || printf possible)"

    if [[ "$private_keys" == "false" ]]; then
      classification="watch-only"
    elif [[ "$private_keys" == "true" ]]; then
      classification="private-keys-enabled"
    else
      classification="unknown"
    fi

    printf '  wallet: %s | classification=%s | descriptors=%s | txcount=%s | scanning=%s\n' \
      "$wallet" "$classification" "${descriptors:-unknown}" "${txcount:-unknown}" "$scanning"
  done < <(printf '%s' "$wallets_json" | sed -n 's/^[[:space:]]*"\(.*\)"[[:space:]]*,\{0,1\}[[:space:]]*$/\1/p')
done

if [[ "$RPC_OK" -eq 0 ]]; then
  info "No accessible Bitcoin Core RPC endpoint was found for the current user."
  info "Run with the Bitcoin service account or sudo for broader read-only visibility."
fi

section "Interpretation"
info "classification=watch-only means Bitcoin Core reports private_keys_enabled=false."
info "A candidate directory alone does not prove that a wallet is active or watch-only."
info "No wallet addresses, descriptors, balances, transactions, seeds, or keys were printed."
