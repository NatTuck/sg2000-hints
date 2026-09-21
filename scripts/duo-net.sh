#!/usr/bin/env bash
set -euo pipefail

PROG=${0##*/}
DUO_VID=3346
DUO_PID=1009
DEF_DUO_IP=10.42.0.1
DEF_HOST_IP=10.42.0.2
NFT_TABLE=duo_nat
TAG=duo-net
HOSTS=/etc/hosts
HOSTS_MARK="# duo-net"
HOSTS_NAME=duos
STATE=/run/duo-net.state
SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes)

IFACE=""
UPLINK=""
UPLINK_GIVEN=0
HOST_IP=""
HOST_IP_GIVEN=0
DUO_IP=$DEF_DUO_IP
DUO_USER=debian
DNS="1.1.1.1 8.8.8.8"
WANT_DHCP=0
DO_ROUTE=1
SUBNET=""
ADDED_ADDR=0
NM_RELEASED=0
PREV_FORWARD=""
NAT_BACKEND=""
FWD_BACKEND=""
ORIG_USER=""
ORIG_HOME=""
cmd=""

log() { printf '%s\n' "$*" >&2; }
die() { log "error: $*"; exit 1; }

usage() {
	cat >&2 <<EOF
usage: sudo $PROG <command> [options]

commands:
  (no command)      same as 'all'
  detect            list Milk-V Duo RNDIS interfaces
  up                bring the link up and give the host an address
  share             enable forwarding and NAT to the internet uplink
  route             point the Duo's default route and DNS at the host
  all               up + share + route (default)
  status            show the current state
  down              remove everything this script added

options:
  --iface IF        Duo RNDIS interface (default: auto-detect)
  --uplink IF       internet uplink (default: device of the default route)
  --host-ip IP      host address on the Duo link (default: reuse, else $DEF_HOST_IP)
  --duo-ip IP       Duo address (default: $DEF_DUO_IP)
  --duo-user USER   SSH user on the Duo (default: $DUO_USER)
  --dns "A B"       DNS servers to set on the Duo (default: $DNS)
  --dhcp            try DHCP before falling back to a static host address
  --no-route        host side only (do not touch the Duo)

notes:
  the default run also points '$HOSTS_NAME' at the board in $HOSTS; 'down' removes that line.
EOF
}

parse_args() {
	while [ $# -gt 0 ]; do
		case "$1" in
			detect|up|share|route|all|status|down) cmd=$1; shift ;;
			help|-h|--help) cmd=help; shift ;;
			--iface) IFACE=${2:?--iface needs a value}; shift 2 ;;
			--uplink) UPLINK=${2:?--uplink needs a value}; UPLINK_GIVEN=1; shift 2 ;;
			--host-ip) HOST_IP=${2:?--host-ip needs a value}; HOST_IP_GIVEN=1; shift 2 ;;
			--duo-ip) DUO_IP=${2:?--duo-ip needs a value}; shift 2 ;;
			--duo-user) DUO_USER=${2:?--duo-user needs a value}; shift 2 ;;
			--dns) DNS=${2:?--dns needs a value}; shift 2 ;;
			--dhcp) WANT_DHCP=1; shift ;;
			--no-route) DO_ROUTE=0; shift ;;
			*) die "unknown argument: $1" ;;
		esac
	done
	[ -n "$cmd" ] || cmd=all
}

require_root() {
	[ "$(id -u)" -eq 0 ] && return 0
	command -v sudo >/dev/null 2>&1 || die "must be run as root (sudo not found)"
	exec sudo -- "$(readlink -f "$0")" "$@"
}

subnet_of() {
	awk -F. '{ print $1"."$2"."$3".0/24" }' <<<"$1"
}

duo_ifaces() {
	local d if vid pid dev drv found=""
	for d in /sys/class/net/*; do
		[ -e "$d" ] || continue
		if=${d##*/}
		[ "$if" = lo ] && continue
		[ -e "$d/device" ] || continue
		dev=$(readlink -f "$d/device" 2>/dev/null || true)
		vid=$(cat "$dev/../idVendor" 2>/dev/null || true)
		pid=$(cat "$dev/../idProduct" 2>/dev/null || true)
		if [ "$vid" = "$DUO_VID" ] && [ "$pid" = "$DUO_PID" ]; then
			found="$found $if"
			continue
		fi
		if [ "$vid" = "$DUO_VID" ] && command -v udevadm >/dev/null 2>&1; then
			drv=$(udevadm info -q property -p "$d" 2>/dev/null | sed -n 's/^ID_USB_DRIVER=//p' || true)
			[ "$drv" = rndis_host ] && found="$found $if"
		fi
	done
	printf '%s' "${found# }"
}

pick_iface() {
	if [ -n "$IFACE" ]; then
		[ -e "/sys/class/net/$IFACE" ] || die "interface $IFACE not found"
		printf '%s' "$IFACE"
		return 0
	fi
	local ifs count
	ifs=$(duo_ifaces)
	[ -n "$ifs" ] || die "no Milk-V Duo RNDIS interface found (USB ${DUO_VID}:${DUO_PID})"
	count=$(printf '%s\n' $ifs | wc -l)
	if [ "$count" -gt 1 ]; then
		log "found multiple Duo interfaces:$ifs"
		die "only one Duo is supported at a time; unplug the others or pass --iface"
	fi
	printf '%s' "$ifs"
}

detect_uplink() {
	ip -4 route show default 2>/dev/null | awk '{ for (i=1;i<=NF;i++) if ($i=="dev") { print $(i+1); exit } }'
}

if_ip() {
	ip -4 -o addr show dev "$1" scope global 2>/dev/null | awk '{ print $4 }' | cut -d/ -f1 | head -n1
}

ensure_addr() {
	local if=$1 ip=$2
	if ! ip -4 addr show dev "$if" | grep -q "inet ${ip}/"; then
		ip addr add "${ip}/24" dev "$if"
		ADDED_ADDR=1
	fi
}

try_dhcp() {
	local if=$1
	if command -v dhclient >/dev/null 2>&1; then
		timeout 15 dhclient -1 -4 "$if" >/dev/null 2>&1 || true
	elif command -v udhcpc >/dev/null 2>&1; then
		timeout 15 udhcpc -i "$if" -n -q -t 3 >/dev/null 2>&1 || true
	else
		log "no DHCP client available; using a static host address"
	fi
}

nm_release() {
	local if=$1 m
	command -v nmcli >/dev/null 2>&1 || return 0
	m=$(nmcli -g GENERAL.NM-MANAGED device show "$if" 2>/dev/null || true)
	if [ "$m" = yes ]; then
		nmcli device set "$if" managed no >/dev/null 2>&1 || true
		NM_RELEASED=1
	fi
}

load_state() {
	[ -f "$STATE" ] || return 0
	local k v
	while IFS='=' read -r k v; do
		case "$k" in
			IFACE) if [ -z "$IFACE" ]; then IFACE=$v; fi ;;
			UPLINK) if [ -z "$UPLINK" ]; then UPLINK=$v; fi ;;
			HOST_IP) if [ -z "$HOST_IP" ]; then HOST_IP=$v; fi ;;
			SUBNET) if [ -z "$SUBNET" ]; then SUBNET=$v; fi ;;
			ADDED_ADDR) if [ "$ADDED_ADDR" = 0 ] && [ -n "$v" ]; then ADDED_ADDR=$v; fi ;;
			NM_RELEASED) if [ "$NM_RELEASED" = 0 ] && [ -n "$v" ]; then NM_RELEASED=$v; fi ;;
			PREV_FORWARD) if [ -z "$PREV_FORWARD" ]; then PREV_FORWARD=$v; fi ;;
			NAT_BACKEND) if [ -z "$NAT_BACKEND" ]; then NAT_BACKEND=$v; fi ;;
			FWD_BACKEND) if [ -z "$FWD_BACKEND" ]; then FWD_BACKEND=$v; fi ;;
		esac
	done <"$STATE"
}

save_state() {
	{
		printf 'IFACE=%s\n' "$IFACE"
		printf 'UPLINK=%s\n' "$UPLINK"
		printf 'HOST_IP=%s\n' "$HOST_IP"
		printf 'SUBNET=%s\n' "$SUBNET"
		printf 'ADDED_ADDR=%s\n' "$ADDED_ADDR"
		printf 'NM_RELEASED=%s\n' "$NM_RELEASED"
		printf 'PREV_FORWARD=%s\n' "$PREV_FORWARD"
		printf 'NAT_BACKEND=%s\n' "$NAT_BACKEND"
		printf 'FWD_BACKEND=%s\n' "$FWD_BACKEND"
	} >"$STATE"
	chmod 600 "$STATE"
}

hosts_set() {
	[ -f "$HOSTS" ] || return 0
	local dir tmp
	dir=$(dirname "$HOSTS")
	tmp=$(mktemp "$dir/.duo-net.hosts.XXXXXX") || return 1
	if awk -v mark="$HOSTS_MARK" -v name="$HOSTS_NAME" '
		{
			line=$0
			sub(/#.*/, "", line)
			n=split(line, f, /[ \t]+/)
			drop=0
			for (i=2; i<=n; i++) if (f[i]==name) drop=1
			if (index($0, mark)) drop=1
			if (!drop) print
		}
	' "$HOSTS" >"$tmp"; then
		printf '%s\t%s\t%s\n' "$DUO_IP" "$HOSTS_NAME" "$HOSTS_MARK" >>"$tmp"
		chmod --reference="$HOSTS" "$tmp" 2>/dev/null || chmod 644 "$tmp"
		chown --reference="$HOSTS" "$tmp" 2>/dev/null || true
		mv "$tmp" "$HOSTS"
		log "set $HOSTS_NAME -> $DUO_IP in $HOSTS"
	else
		rm -f "$tmp"
		return 1
	fi
}

hosts_remove() {
	[ -f "$HOSTS" ] || return 0
	local dir tmp
	dir=$(dirname "$HOSTS")
	tmp=$(mktemp "$dir/.duo-net.hosts.XXXXXX") || return 1
	if awk -v mark="$HOSTS_MARK" 'index($0, mark) == 0' "$HOSTS" >"$tmp"; then
		chmod --reference="$HOSTS" "$tmp" 2>/dev/null || chmod 644 "$tmp"
		chown --reference="$HOSTS" "$tmp" 2>/dev/null || true
		mv "$tmp" "$HOSTS"
		log "removed $HOSTS_MARK entries from $HOSTS"
	else
		rm -f "$tmp"
		return 1
	fi
}

delete_ipt_by_comment() {
	local table=$1 chain=$2 num
	command -v iptables >/dev/null 2>&1 || return 0
	while :; do
		num=$(iptables -w -t "$table" -S "$chain" 2>/dev/null | grep -n -- "$TAG" | head -n1 | cut -d: -f1 || true)
		[ -n "$num" ] || break
		iptables -w -t "$table" -D "$chain" "$((num - 1))" 2>/dev/null || break
	done
}

add_fwd_rule() {
	if ! iptables -w -C FORWARD "$@" -m comment --comment "$TAG" -j ACCEPT 2>/dev/null; then
		iptables -w -I FORWARD 1 "$@" -m comment --comment "$TAG" -j ACCEPT
	fi
}

add_nat() {
	if command -v nft >/dev/null 2>&1; then
		nft delete table inet "$NFT_TABLE" 2>/dev/null || true
		nft -f - <<EOF
table inet $NFT_TABLE {
	chain postrouting {
		type nat hook postrouting priority srcnat; policy accept;
		oifname "$UPLINK" ip saddr $SUBNET masquerade
	}
}
EOF
		NAT_BACKEND=nft
	else
		command -v iptables >/dev/null 2>&1 || die "neither nft nor iptables is available"
		delete_ipt_by_comment nat POSTROUTING
		iptables -w -t nat -A POSTROUTING -s "$SUBNET" -o "$UPLINK" -m comment --comment "$TAG" -j MASQUERADE
		NAT_BACKEND=iptables
	fi
}

add_fwd() {
	if command -v iptables >/dev/null 2>&1; then
		delete_ipt_by_comment filter FORWARD
		add_fwd_rule -i "$IFACE" -o "$UPLINK" -s "$SUBNET"
		add_fwd_rule -i "$UPLINK" -o "$IFACE" -d "$SUBNET" -m conntrack --ctstate RELATED,ESTABLISHED
		FWD_BACKEND=iptables
	elif command -v nft >/dev/null 2>&1; then
		nft add chain inet "$NFT_TABLE" forward '{ type filter hook forward priority 0; policy accept; }' 2>/dev/null || true
		nft add rule inet "$NFT_TABLE" forward iifname "$IFACE" oifname "$UPLINK" ip saddr "$SUBNET" accept 2>/dev/null || true
		nft add rule inet "$NFT_TABLE" forward iifname "$UPLINK" oifname "$IFACE" ip daddr "$SUBNET" ct state related,established accept 2>/dev/null || true
		FWD_BACKEND=nft
	else
		die "no firewall tool (iptables/nft) is available"
	fi
}

run_ssh() {
	if [ "$(id -u)" -eq 0 ] && [ "$ORIG_USER" != root ]; then
		if [ -f "$ORIG_HOME/.ssh/id_ed25519" ]; then
			sudo -u "$ORIG_USER" env HOME="$ORIG_HOME" ssh -i "$ORIG_HOME/.ssh/id_ed25519" "${SSH_OPTS[@]}" "$@"
		else
			sudo -u "$ORIG_USER" env HOME="$ORIG_HOME" ssh "${SSH_OPTS[@]}" "$@"
		fi
	else
		ssh "${SSH_OPTS[@]}" "$@"
	fi
}

wait_for_duo() {
	local tries=$1 i=1
	while [ "$i" -le "$tries" ]; do
		if ping -c1 -W2 "$DUO_IP" >/dev/null 2>&1; then
			return 0
		fi
		i=$((i + 1))
		sleep 1
	done
	return 1
}

ssh_retry() {
	local tries=$1 rc=0 i=1
	shift
	while :; do
		run_ssh "$@" && return 0
		rc=$?
		[ "$rc" -eq 255 ] || return "$rc"
		[ "$i" -ge "$tries" ] && return "$rc"
		i=$((i + 1))
		sleep 3
	done
}

cmd_detect() {
	local ifs
	ifs=$(duo_ifaces)
	if [ -z "$ifs" ]; then
		log "no Milk-V Duo RNDIS interface found"
		return 1
	fi
	printf '%s\n' $ifs
}

cmd_up() {
	IFACE=$(pick_iface)
	load_state
	if [ "$UPLINK_GIVEN" = 0 ]; then
		UPLINK=$(detect_uplink)
	fi
	[ -n "$UPLINK" ] || die "no default route found; pass --uplink"
	SUBNET=$(subnet_of "$DUO_IP")
	ip link show "$IFACE" >/dev/null 2>&1 || die "interface $IFACE vanished"
	ip link set "$IFACE" up
	nm_release "$IFACE"
	if [ "$HOST_IP_GIVEN" = 1 ]; then
		ensure_addr "$IFACE" "$HOST_IP"
	else
		HOST_IP=$(if_ip "$IFACE")
		if [ -z "$HOST_IP" ] && [ "$WANT_DHCP" = 1 ]; then
			try_dhcp "$IFACE"
			HOST_IP=$(if_ip "$IFACE")
		fi
		if [ -z "$HOST_IP" ]; then
			HOST_IP=$DEF_HOST_IP
			ensure_addr "$IFACE" "$HOST_IP"
		fi
	fi
	save_state
	hosts_set || log "warning: could not update $HOSTS"
	log "host address on $IFACE: $HOST_IP"
	if wait_for_duo 10; then
		log "Duo $DUO_IP is reachable"
	else
		log "warning: Duo $DUO_IP did not answer ping (continuing)"
	fi
}

cmd_share() {
	load_state
	[ -n "$IFACE" ] || IFACE=$(pick_iface)
	[ -n "$UPLINK" ] || UPLINK=$(detect_uplink)
	[ -n "$UPLINK" ] || die "no default route found; pass --uplink"
	[ -n "$SUBNET" ] || SUBNET=$(subnet_of "$DUO_IP")
	[ -n "$HOST_IP" ] || HOST_IP=$(if_ip "$IFACE" || true)
	if [ -z "$PREV_FORWARD" ]; then
		PREV_FORWARD=$(sysctl -n net.ipv4.ip_forward 2>/dev/null || echo 0)
	fi
	sysctl -q -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || die "could not enable net.ipv4.ip_forward"
	add_nat
	add_fwd
	save_state
	log "sharing $SUBNET to the internet via $UPLINK (nat=$NAT_BACKEND fwd=$FWD_BACKEND)"
}

cmd_route() {
	load_state
	[ -n "$IFACE" ] || IFACE=$(pick_iface)
	[ -n "$HOST_IP" ] || HOST_IP=$(if_ip "$IFACE" || true)
	[ -n "$HOST_IP" ] || die "no host address on $IFACE; run 'up' first"
	local target="$DUO_USER@$DUO_IP"
	log "pointing $target default route at $HOST_IP"
	ssh_retry 6 "$target" "sudo ip route replace default via $HOST_IP dev usb0" ||
		die "could not set the Duo default route (is passwordless SSH set up for $target?)"
	run_ssh "$target" "sudo chattr -i /etc/resolv.conf 2>/dev/null || true; printf 'nameserver %s\n' $DNS | sudo tee /etc/resolv.conf >/dev/null" ||
		log "warning: could not write /etc/resolv.conf on the Duo"
	run_ssh "$target" "if command -v resolvectl >/dev/null 2>&1 && systemctl is-active --quiet systemd-resolved 2>/dev/null; then sudo resolvectl dns usb0 $DNS; sudo resolvectl domain usb0 '~.'; fi" >/dev/null 2>&1 || true
	if run_ssh "$target" "ping -c1 -W3 1.1.1.1 >/dev/null 2>&1"; then
		log "Duo has internet (ping 1.1.1.1 ok)"
	else
		log "warning: Duo cannot ping 1.1.1.1"
	fi
	if run_ssh "$target" "getent hosts deb.debian.org >/dev/null 2>&1"; then
		log "Duo DNS works"
	else
		log "warning: Duo DNS lookup failed"
	fi
}

cmd_status() {
	load_state
	echo "interface: ${IFACE:-<none>}"
	echo "uplink:    ${UPLINK:-<none>}"
	echo "host ip:   ${HOST_IP:-<none>}"
	echo "duo ip:    ${DUO_IP:-<none>}"
	if [ -n "$IFACE" ] && [ -e "/sys/class/net/$IFACE" ]; then
		ip -4 -o addr show dev "$IFACE" | awk '{ print "  addr:    "$4 }'
	fi
	if command -v nft >/dev/null 2>&1 && nft list table inet "$NFT_TABLE" >/dev/null 2>&1; then
		echo "nat:       nft table inet $NFT_TABLE present"
	else
		echo "nat:       no nft table"
	fi
	if command -v iptables >/dev/null 2>&1; then
		local n
		n=$(iptables -w -S FORWARD 2>/dev/null | grep -c -- "$TAG" || true)
		echo "forward:   $n iptables rule(s) tagged $TAG"
	fi
	if [ -n "$IFACE" ] && ping -c1 -W2 "$DUO_IP" >/dev/null 2>&1; then
		echo "duo:       reachable"
	else
		echo "duo:       unreachable"
	fi
}

cmd_down() {
	load_state
	if command -v nft >/dev/null 2>&1; then
		nft delete table inet "$NFT_TABLE" 2>/dev/null || true
	fi
	delete_ipt_by_comment filter FORWARD
	delete_ipt_by_comment nat POSTROUTING
	if [ "$ADDED_ADDR" = 1 ] && [ -n "$HOST_IP" ] && [ -n "$IFACE" ]; then
		ip addr del "${HOST_IP}/24" dev "$IFACE" 2>/dev/null || true
	fi
	if [ "$NM_RELEASED" = 1 ] && [ -n "$IFACE" ] && command -v nmcli >/dev/null 2>&1; then
		nmcli device set "$IFACE" managed yes >/dev/null 2>&1 || true
	fi
	if [ -n "$PREV_FORWARD" ]; then
		sysctl -q -w "net.ipv4.ip_forward=$PREV_FORWARD" >/dev/null 2>&1 || true
	fi
	hosts_remove || log "warning: could not update $HOSTS"
	rm -f "$STATE"
	log "removed duo-net host configuration"
}

parse_args "$@"

case "$cmd" in
	help) usage; exit 0 ;;
	detect) cmd_detect; exit $? ;;
esac

require_root "$@"

ORIG_USER=${SUDO_USER:-$(id -un)}
ORIG_HOME=$(getent passwd "$ORIG_USER" 2>/dev/null | cut -d: -f6 || true)
[ -n "$ORIG_HOME" ] || ORIG_HOME=/root

case "$cmd" in
	up) cmd_up ;;
	share) cmd_share ;;
	route) cmd_route ;;
	all)
		cmd_up
		cmd_share
		if [ "$DO_ROUTE" = 1 ]; then
			cmd_route
			log "done: $DUO_USER@$DUO_IP should now have internet"
		fi
		;;
	status) cmd_status ;;
	down) cmd_down ;;
	*) usage; exit 1 ;;
esac
