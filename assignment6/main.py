import re
import sys
import subprocess
import requests

_HOP_RE = re.compile(r'\s*(\d+)\s+(.*)')
_PROBE_RE = re.compile(
    r'\*|'
    r'(\S+) \((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)|'
    r'(\d+\.\d+)\s*ms',
)


def parse_probe_line(line: str) -> dict | None:
    m = _HOP_RE.match(line)
    if not m:
        return None
    hop_num = int(m.group(1))
    rest = m.group(2)

    probes = []
    current_host = None
    current_ip = None

    for token in _PROBE_RE.finditer(rest):
        if token.group(0) == '*':
            probes.append({'hostname': None, 'ip': None, 'rtt_ms': None})
        elif token.group(1) is not None:
            current_host = token.group(1) if token.group(1) != token.group(2) else None
            current_ip = token.group(2)
        elif token.group(3) is not None:
            probes.append({
                'hostname': current_host,
                'ip': current_ip,
                'rtt_ms': float(token.group(3)),
            })

    return {'hop': hop_num, 'probes': probes}


def _is_public_ip(ip: str) -> bool:
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    first = int(parts[0])
    if first == 10:
        return False
    if first == 172 and 16 <= int(parts[1]) <= 31:
        return False
    if first == 192 and int(parts[1]) == 168:
        return False
    return True


_GW_API = 'https://api.thegreenwebfoundation.org/api/v3/ip-to-co2intensity'
_gw_cache: dict[str, dict] = {}
_ip_to_public: dict[str, str] = {}


def _build_ip_inheritance(hops: list[dict]) -> list[str]:
    """Walk hops in route order, mapping private IPs to their nearest public IP by
    probe position.  For equal-distance ties the upstream (earlier) public wins,
    since that is the likely NAT gateway."""
    all_ips = [p['ip'] for h in hops for p in h['probes'] if p['ip']]

    public_positions: list[tuple[int, str]] = [
        (i, ip) for i, ip in enumerate(all_ips) if _is_public_ip(ip)
    ]

    ordered_publics: list[str] = []
    for _, ip in public_positions:
        if ip not in ordered_publics:
            ordered_publics.append(ip)
        if ip not in _gw_cache:
            _gw_cache[ip] = None

    first_public = public_positions[0][1] if public_positions else None
    if first_public is None:
        return ordered_publics

    for i, ip in enumerate(all_ips):
        if _is_public_ip(ip) or ip in _ip_to_public:
            continue
        best = first_public
        best_dist = float('inf')
        for pos, pub_ip in public_positions:
            dist = abs(i - pos)
            if dist < best_dist or (dist == best_dist and pos < i):
                best_dist = dist
                best = pub_ip
        _ip_to_public[ip] = best

    return ordered_publics


def get_carbon_intensity(ip: str) -> dict | None:
    if not ip:
        return None

    lookup_ip = _ip_to_public.get(ip, ip)

    cached = _gw_cache.get(lookup_ip)
    if cached is not None:
        return cached

    try:
        r = requests.get(f'{_GW_API}/{lookup_ip}', timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        ci = data.get('carbon_intensity')
        if ci is not None:
            result = {
                'carbon_intensity': ci,
                'country': data.get('country_name'),
                'year': data.get('year'),
            }
            _gw_cache[lookup_ip] = result
            return result
    except requests.RequestException:
        pass
    _gw_cache[lookup_ip] = None
    return None



# ── Energy model: Sustainable Web Design v4 ──────────────────────────────────
#
# This model estimates the energy consumed by the *transport path only*:
#   routers along the route, NICs at each end, and DC networking equipment.
#
# Included:
#   - Router forwarding energy (per hop, split evenly)
#   - NIC transmission/reception energy (absorbed into the per-hop split)
#   - DC switching/routing gear that processes packets at the destination
#
# Excluded:
#   - Server request processing  (CPU, memory, storage at google.com)
#   - Client device processing   (CPU, display, local NIC overhead)
#   - DC cooling, UPS, lighting  (overhead is proportionally excluded)
#   - Embodied/manufacturing of networking hardware  (handled separately)
#
# Source: Sustainable Web Design Model v4
#   https://sustainablewebdesign.org/estimating-digital-emissions/
#
# Global network operational energy: 310 TWh/yr  (IEA 2022)
# Global DC operational energy:      290 TWh/yr  (IEA 2022)
# Global internet traffic:           5.29 ZB/yr  (ITU 2023)
#
# Network operational  intensity = 310 TWh / 5.29 ZB = 0.059 kWh/GB
# Network embodied     intensity =  68 TWh / 5.29 ZB = 0.013 kWh/GB  (Malmodin 2023)
# DC operational       intensity = 290 TWh / 5.29 ZB = 0.055 kWh/GB
# DC embodied          intensity =  62 TWh / 5.29 ZB = 0.012 kWh/GB  (Malmodin 2023)
#
# Assumptions / caveats:
#   1. Energy is spread evenly across all hops.  In reality, core routers
#      consume more power than access routers; we lack per-hop hardware data.
#   2. NIC energy is not itemised — it is included in the per-hop network
#      average, since NIC power is part of the global network total (310 TWh).
#   3. DC networking is estimated at 25 % of total DC energy, based on
#      typical DC power breakdowns (networking ≈ 10-15 % of IT load, IT load
#      ≈ 50-60 % of total DC).  This is a rough heuristic.
#   4. Silent (non-responding) hops are counted toward the hop total but
#      use the averaged energy — they still exist and forward traffic.
#   5. Annual average intensities from Ember (via Green Web Foundation API)
#      are used per-hop.  Real-time marginal intensity would differ.
#   6. Embodied (manufacturing) energy is included as a fixed percentage of
#      operational energy per the Malmodin 2023 lifecycle analysis.
#   7. The return path is assumed to follow the same route and consume
#      the same energy as the forward path (symmetric routing assumption).
#
_DATA_BYTES = 1_000_000  # Default: 1 MB request + response

_NET_OP_KWH_PER_GB = 0.059
_NET_EM_KWH_PER_GB = 0.013
_DC_OP_KWH_PER_GB = 0.055
_DC_EM_KWH_PER_GB = 0.012
_DC_NET_FRAC = 0.25  # fraction of DC energy attributed to networking gear


def bytes_to_gb(b: int) -> float:
    return b / (1024 ** 3)


def estimate_request_energy(
    data_bytes: int,
    visible_hop_ips: list[str],
    hidden_hop_count: int = 0,
) -> dict:
    total_hops = len(visible_hop_ips) + hidden_hop_count
    if total_hops == 0:
        return {}

    data_gb = bytes_to_gb(data_bytes)

    net_energy_kwh = data_gb * (_NET_OP_KWH_PER_GB + _NET_EM_KWH_PER_GB)
    dc_net_energy_kwh = data_gb * (_DC_OP_KWH_PER_GB + _DC_EM_KWH_PER_GB) * _DC_NET_FRAC

    per_hop_net_kwh = net_energy_kwh / total_hops if total_hops else 0

    hop_details = []
    for ip in visible_hop_ips:
        ci_data = get_carbon_intensity(ip)
        ci = (ci_data.get('carbon_intensity', 0) / 1000) if ci_data else 0
        hop_energy = per_hop_net_kwh
        hop_carbon_kg = hop_energy * ci
        hop_details.append({
            'ip': ip,
            'energy_kwh': hop_energy,
            'carbon_g': hop_carbon_kg * 1000,
            'ci': ci * 1000,
        })

    total_net_carbon_kg = sum(h['carbon_g'] for h in hop_details) / 1000

    dest_ci_data = get_carbon_intensity(visible_hop_ips[-1]) if visible_hop_ips else None
    dest_ci = (dest_ci_data.get('carbon_intensity', 0) / 1000) if dest_ci_data else 0
    dc_carbon_kg = dc_net_energy_kwh * dest_ci

    total_carbon_g = total_net_carbon_kg * 1000 + dc_carbon_kg * 1000

    return {
        'data_mb': data_bytes / (1024 * 1024),
        'total_hops': total_hops,
        'hop_details': hop_details,
        'network_energy_kwh': net_energy_kwh,
        'dc_net_energy_kwh': dc_net_energy_kwh,
        'total_energy_kwh': net_energy_kwh + dc_net_energy_kwh,
        'network_carbon_g': total_net_carbon_kg * 1000,
        'dc_carbon_g': dc_carbon_kg * 1000,
        'total_carbon_g': total_carbon_g,
    }


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'google.com'

    exec_result = subprocess.run(['traceroute', target], capture_output=True)
    lines = exec_result.stdout.decode().splitlines()[1:]

    hops = [parse_probe_line(line) for line in lines]
    visible_ips = _build_ip_inheritance(hops)

    hidden = sum(1 for h in hops if all(p['ip'] is None for p in h['probes']))
    estimate = estimate_request_energy(_DATA_BYTES, visible_ips, hidden)

    if estimate:
        print(f"Transport energy estimate for {estimate['data_mb']:.1f} MB request to {target}\n")
        print(f"  Route: {len(visible_ips)} visible + {hidden} silent = {estimate['total_hops']} hops")
        print(f"  Network energy:      {estimate['network_energy_kwh']:.6f} kWh")
        print(f"  DC networking:       {estimate['dc_net_energy_kwh']:.6f} kWh")
        print(f"  Total transport:     {estimate['total_energy_kwh']:.6f} kWh")
        print(f"  Network carbon:      {estimate['network_carbon_g']:.3f} gCO₂")
        print(f"  DC networking carb:  {estimate['dc_carbon_g']:.3f} gCO₂")
        print(f"  Total transport CO₂: {estimate['total_carbon_g']:.3f} gCO₂")
        print()
        print("  Per-hop breakdown:")
        for hd in estimate['hop_details']:
            ci_data = get_carbon_intensity(hd['ip'])
            country = ci_data.get('country', '') if ci_data else ''
            print(f"    {hd['ip']:20s} {country:35s} {hd['energy_kwh']:.6f} kWh  × {hd['ci']:.0f} gCO₂/kWh = {hd['carbon_g']:.6f} gCO₂")


if __name__ == '__main__':
    main()
