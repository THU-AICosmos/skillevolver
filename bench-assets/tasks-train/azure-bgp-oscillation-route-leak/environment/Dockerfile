FROM python:3.11-slim

# Create directories
RUN mkdir -p /app/data /app/output /app/environment/data

# Generate test data for Azure Virtual WAN BGP topology (train variant)
RUN python << 'DATAGEN'
import json
import random

# Azure Virtual WAN Topology (train variant - distinct from val):
#
#          ASN 64810 (Virtual WAN / Regional ISP)
#         /                    \
#    ASN 64811              ASN 64812
#    (HubEast/vhubvnetEast)  (HubWest/vhubvnetWest)
#    /         \              /         \
# ASN 64813  ASN 64814   ASN 64815  ASN 64816
# (vnetA)    (vnetB)     (vnetC)    (vnetD - origin)

bgp_topology = {
    "connections": [
        {"from": 64810, "to": 64811},
        {"from": 64810, "to": 64812},
        {"from": 64811, "to": 64813},
        {"from": 64811, "to": 64814},
        {"from": 64812, "to": 64815},
        {"from": 64812, "to": 64816},
        {"from": 64811, "to": 64812}
    ]
}

# Origin route (customer prefix from vnetD)
origin_route = {
    "prefix": "10.7.4.0/24",
    "origin_asn": 64816,
    "description": "Customer prefix from vnetD (Azure Virtual WAN train variant)"
}

# Routing preferences causing oscillation:
# HubEast prefers via HubWest and vice versa
routing_preferences = {
    64811: {"prefer_via": 64812, "description": "HubEast (vhubvnetEast) prefers routes via HubWest (vhubvnetWest)"},
    64812: {"prefer_via": 64811, "description": "HubWest (vhubvnetWest) prefers routes via HubEast (vhubvnetEast)"}
}

# AS relationships (standard BGP hierarchy)
as_relationships = [
    {"from": 64810, "to": 64811, "type": "provider", "description": "Virtual WAN provides transit to HubEast (vhubvnetEast)"},
    {"from": 64810, "to": 64812, "type": "provider", "description": "Virtual WAN provides transit to HubWest (vhubvnetWest)"},
    {"from": 64811, "to": 64813, "type": "provider", "description": "HubEast provides transit to vnetA"},
    {"from": 64811, "to": 64814, "type": "provider", "description": "HubEast provides transit to vnetB"},
    {"from": 64812, "to": 64815, "type": "provider", "description": "HubWest provides transit to vnetC"},
    {"from": 64812, "to": 64816, "type": "provider", "description": "HubWest provides transit to vnetD (origin)"},
    {"from": 64811, "to": 64810, "type": "customer", "description": "HubEast is customer of Virtual WAN"},
    {"from": 64812, "to": 64810, "type": "customer", "description": "HubWest is customer of Virtual WAN"},
    {"from": 64813, "to": 64811, "type": "customer", "description": "vnetA is customer of HubEast"},
    {"from": 64814, "to": 64811, "type": "customer", "description": "vnetB is customer of HubEast"},
    {"from": 64815, "to": 64812, "type": "customer", "description": "vnetC is customer of HubWest"},
    {"from": 64816, "to": 64812, "type": "customer", "description": "vnetD is customer of HubWest"},
    {"from": 64811, "to": 64812, "type": "peer", "description": "HubEast peers with HubWest"},
    {"from": 64812, "to": 64811, "type": "peer", "description": "HubWest peers with HubEast"}
]

# Local preference rules
local_preference = {
    "customer": 200,
    "peer": 100,
    "provider": 50,
    "description": "Standard local preference: customer routes preferred over peer, peer over provider"
}

# Route event: HubEast (64811) announces routes from provider (Virtual WAN 64810) to peer (HubWest 64812)
route_events = [
    {
        "advertiser_asn": 64811,
        "source_asn": 64810,
        "destination_asn": 64812,
        "source_type": "provider",
        "destination_type": "peer",
        "description": "HubEast (vhubvnetEast) advertised routes from provider (Virtual WAN) to peer (HubWest/vhubvnetWest)"
    }
]

# All possible solutions for the agent to evaluate
possible_solutions = [
    "Change BGP keepalive timer of vhubvnetEast to 30 seconds and holdtime to 90 seconds",
    "Configure export policy on vhubvnetEast (ASN 64811) to block announcing provider routes (from Virtual WAN ASN 64810) to peer vhubvnetWest (ASN 64812)",
    "Enable route dampening on vhubvnetEast S2S VPN Gateway with penalty threshold 1500 and suppress limit 3000",
    "Update routing preference on hubEast (ASN 64811) to stop preferring routes via hubWest (ASN 64812)",
    "Configure vhubvnetEast to prefer shorter AS-PATH length or use MED value 250 for route selection",
    "Enable ingress filtering on vhubvnetWest (ASN 64812) to reject routes with AS_PATH containing Virtual WAN ASN 64810 when received from peer vhubvnetEast",
    "Enable ECMP load balancing across hubEast and hubWest with equal-cost multipath",
    "Configure export policy on hubEast to filter out routes learned from hubWest before re-advertising",
    "Deploy Route Map in hubEast with centralized routing management",
    "Enable RPKI origin validation on vhubvnetWest to verify prefix 10.7.4.0/24 originates from ASN 64816 (vnetD)",
    "Restart BGP session on hubEast ",
    "Set route preference hierarchy on hubEast: customer routes (vnetA, vnetB) > Virtual WAN routes > peer routes (vhubvnetWest)",
    "disable hub peering between vhubvnetEast and vhubvnetWest",
    "Configure route policy on vhubvnetEast to enforce no-export of provider routes to peer vhubvnetWest by bgp community",
    "Apply route filter on vhubvnetEast to only accept prefixes 10.7.0.0/16 from vhubvnetWest",
    "Configure user defined route override on vhubvnetEast defaultRouteTable to prefer specific next-hop",
    "Wait for Virtual WAN automatic convergence or ASN 64812 to change AS_PATH length of routes",
    "Enable Virtual WAN hub routing intent to enforce all hub-to-hub routes go through Virtual WAN (ASN 64810) only",
    "Set maximum-prefix limit of 25 prefixes on BGP session between vhubvnetEast and vhubvnetWest",
]

random.seed(73)
random.shuffle(possible_solutions)

# Save all data files
with open('/app/data/topology.json', 'w', encoding='utf-8') as f:
    json.dump(bgp_topology, f, indent=2)

with open('/app/data/route.json', 'w', encoding='utf-8') as f:
    json.dump(origin_route, f, indent=2)

with open('/app/data/preferences.json', 'w', encoding='utf-8') as f:
    json.dump(routing_preferences, f, indent=2)

with open('/app/data/relationships.json', 'w', encoding='utf-8') as f:
    json.dump(as_relationships, f, indent=2)

with open('/app/data/local_pref.json', 'w', encoding='utf-8') as f:
    json.dump(local_preference, f, indent=2)

with open('/app/data/route_events.json', 'w', encoding='utf-8') as f:
    json.dump(route_events, f, indent=2)

with open('/app/data/possible_solutions.json', 'w', encoding='utf-8') as f:
    json.dump(possible_solutions, f, indent=2)

print("Generated Azure Virtual WAN BGP topology and configuration files in /app/data/ (train variant)")

DATAGEN

WORKDIR /app
