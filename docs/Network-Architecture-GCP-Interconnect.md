# Network Architecture Design: GCP Dedicated Interconnect for Contact Center AI

**Document Version:** 1.0  
**Date:** 2024-01-15  
**Classification:** Confidential - Internal Use Only  
**Author:** Network Engineering Team  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [GCP Region Selection](#2-gcp-region-selection)
3. [Network Topology Diagram](#3-network-topology-diagram)
4. [Dedicated Interconnect Design](#4-dedicated-interconnect-design)
5. [BGP Routing Design](#5-bgp-routing-design)
6. [GCP VPC Network Design](#6-gcp-vpc-network-design)
7. [Voice Path Architecture](#7-voice-path-architecture)
8. [Data Path Architecture](#8-data-path-architecture)
9. [Five9 Connectivity](#9-five9-connectivity)
10. [VPC Service Controls](#10-vpc-service-controls)
11. [Firewall Rules](#11-firewall-rules)
12. [Bandwidth Calculation](#12-bandwidth-calculation)
13. [High Availability & DR](#13-high-availability--dr)
14. [Latency Analysis](#14-latency-analysis)
15. [Implementation Checklist](#15-implementation-checklist)
16. [Cost Estimate (Monthly)](#16-cost-estimate-monthly)

---

## 1. Executive Summary

This document defines the network architecture for establishing private, high-availability connectivity between dual on-premises data centers and Google Cloud Platform (GCP) to support a Contact Center AI (CCAI) deployment integrated with Genesys on-premises infrastructure.

**Key Design Objectives:**

- **Private Connectivity:** Dual data center (Dallas TX primary, Phoenix AZ DR) to GCP via Dedicated Interconnect — all voice and data traffic remains on private networks per regulatory requirements (no public internet traversal for voice)
- **99.99% Availability SLA:** Achieved through redundant 10 Gbps Dedicated Interconnect connections across diverse facilities in both metros (4 total physical links)
- **Low-Latency Voice Path:** On-prem Oracle SBC → GCP Google Telephony Platform (GTP) → Dialogflow CX/CCAI → return to Genesys on-prem, with end-to-end one-way latency target of < 80ms
- **Real-Time Data Integration:** Genesys ORS → GCP Cloud Run middleware for call routing decisions during live calls
- **Security:** VPC Service Controls perimeter, no public IP exposure, private Google Access for all GCP services

**Traffic Volume:** 10,000 calls/day with ~50 concurrent calls at peak and 7 API calls/minute for middleware integration.

---

## 2. GCP Region Selection

| Attribute | Primary Region | Secondary/DR Region |
|-----------|---------------|-------------------|
| **GCP Region** | us-south1 (Dallas, TX) | us-central1 (Council Bluffs, Iowa) |
| **Role** | Production workloads | Disaster Recovery / Failover |
| **Proximity to DC** | Same metro as Dallas DC (< 2ms) | ~15-20ms from Phoenix DC |
| **CCAI/Dialogflow CX** | Full support | Full support |
| **Cloud Run** | Available | Available |
| **Speech-to-Text** | Available | Available |
| **Text-to-Speech** | Available | Available |
| **Interconnect Facility** | Equinix DA7, Equinix DA2 | Equinix PH1, DataBank PHX1 (via Phoenix) |
| **GTP Availability** | Yes | Yes |

**Region Selection Rationale:**

1. **us-south1 (Dallas):** Co-located in the same metropolitan area as the primary data center, providing sub-2ms interconnect latency. Full CCAI service availability including Dialogflow CX, STT, and TTS.
2. **us-central1 (Iowa):** Selected for DR due to full CCAI/Dialogflow CX support, geographic diversity from primary, and accessibility from Phoenix DC via interconnect. While not in the same metro as Phoenix, it provides the required service availability that Arizona-based GCP regions may lack for CCAI.

---


## 3. Network Topology Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    NETWORK TOPOLOGY - OVERVIEW                                           │
│                                                                                                         │
│  ╔══════════════════════════╗          CARRIER DARK FIBER          ╔═══════════════════════════════════╗ │
│  ║   DALLAS DATA CENTER    ║         (AT&T / Verizon)             ║      GCP us-south1 (Dallas)       ║ │
│  ║      (PRIMARY)          ║                                      ║                                   ║ │
│  ║                         ║    ┌──────────────────────────┐      ║  ┌─────────────────────────────┐  ║ │
│  ║  ┌─────────────────┐   ║    │    Equinix DA7 (Primary) │      ║  │  Cloud Router (us-south1)   │  ║ │
│  ║  │  Oracle SBC     │   ║    │  ┌────────────────────┐  │      ║  │  BGP ASN: 16550             │  ║ │
│  ║  │  (HA Pair)      │───╫────┼──│ Cross-Connect #1   │──┼──────╫──│  ┌─────────────────────┐    │  ║ │
│  ║  │  SIP/RTP GW     │   ║    │  │ 10 Gbps Dedicated  │  │      ║  │  │ VLAN: voice-vlan    │    │  ║ │
│  ║  └────────┬────────┘   ║    │  └────────────────────┘  │      ║  │  │ VLAN: data-vlan     │    │  ║ │
│  ║           │             ║    └──────────────────────────┘      ║  │  └─────────────────────┘    │  ║ │
│  ║  ┌────────┴────────┐   ║                                      ║  └─────────────────────────────┘  ║ │
│  ║  │ Genesys SIP Svr │   ║    ┌──────────────────────────┐      ║                                   ║ │
│  ║  │ Genesys ORS     │───╫────┼──│ Equinix DA2 (Second.) │      ║  ┌─────────────────────────────┐  ║ │
│  ║  │ CTI/Routing     │   ║    │  ┌────────────────────┐  │      ║  │  contact-center-vpc         │  ║ │
│  ║  └─────────────────┘   ║    │  │ Cross-Connect #2   │──┼──────╫──│                             │  ║ │
│  ║                         ║    │  │ 10 Gbps Dedicated  │  │      ║  │  ┌───────────────────────┐  │  ║ │
│  ╚══════════════════════════╝    │  └────────────────────┘  │      ║  │  │ voice-subnet          │  │  ║ │
│                                  └──────────────────────────┘      ║  │  │ 10.100.0.0/24         │  │  ║ │
│                                                                    ║  │  │ • GTP Endpoint        │  │  ║ │
│  ╔══════════════════════════╗                                      ║  │  │ • SBC Proxy           │  │  ║ │
│  ║  PHOENIX DATA CENTER    ║                                      ║  │  └───────────────────────┘  │  ║ │
│  ║      (DR)               ║                                      ║  │                             │  ║ │
│  ║                         ║    ┌──────────────────────────┐      ║  │  ┌───────────────────────┐  │  ║ │
│  ║  ┌─────────────────┐   ║    │   Equinix PH1 (Primary)  │      ║  │  │ data-subnet           │  │  ║ │
│  ║  │  Oracle SBC     │   ║    │  ┌────────────────────┐  │      ║  │  │ 10.101.0.0/24         │  │  ║ │
│  ║  │  (DR Replica)   │───╫────┼──│ Cross-Connect #3   │──┼──┐   ║  │  │ • Cloud Run (MW)      │  │  ║ │
│  ║  └────────┬────────┘   ║    │  │ 10 Gbps Dedicated  │  │  │   ║  │  │ • Firestore           │  │  ║ │
│  ║           │             ║    │  └────────────────────┘  │  │   ║  │  └───────────────────────┘  │  ║ │
│  ║  ┌────────┴────────┐   ║    └──────────────────────────┘  │   ║  │                             │  ║ │
│  ║  │ Genesys (DR)    │   ║                                  │   ║  │  ┌───────────────────────┐  │  ║ │
│  ║  │ ORS / SIP (DR)  │───╫──┐ ┌──────────────────────────┐ │   ║  │  │ ccai-subnet           │  │  ║ │
│  ║  └─────────────────┘   ║  │ │  DataBank PHX1 (Second.) │ │   ║  │  │ 10.102.0.0/24         │  │  ║ │
│  ║                         ║  └─┼──┌────────────────────┐  │ │   ║  │  │ • Dialogflow CX       │  │  ║ │
│  ╚══════════════════════════╝    │  │ Cross-Connect #4   │──┼─┘   ║  │  │ • STT / TTS           │  │  ║ │
│                                  │  │ 10 Gbps Dedicated  │  │     ║  │  └───────────────────────┘  │  ║ │
│                                  │  └────────────────────┘  │     ║  │                             │  ║ │
│                                  └──────────────────────────┘     ║  └─────────────────────────────┘  ║ │
│                                                                    ╚═══════════════════════════════════╝ │
│                                                                                                         │
│  ╔═══════════════════╗                                             ╔═══════════════════════════════════╗ │
│  ║   Five9 Cloud     ║                                             ║    GCP us-central1 (Iowa) - DR    ║ │
│  ║                   ║──── TLS/SRTP (Internet) ────┐               ║                                   ║ │
│  ║  IVR Front-End    ║    OR Equinix Fabric        │               ║  ┌─────────────────────────────┐  ║ │
│  ╚═══════════════════╝                             │               ║  │  voice-subnet-dr            │  ║ │
│         │                                          │               ║  │  10.100.1.0/24              │  ║ │
│         └──────── Connects to Oracle SBC ──────────┘               ║  │  data-subnet-dr             │  ║ │
│                   (SBC is demarcation point)                        ║  │  10.101.1.0/24              │  ║ │
│                                                                    ║  │  ccai-subnet-dr             │  ║ │
│                                                                    ║  │  10.102.1.0/24              │  ║ │
│                                                                    ║  └─────────────────────────────┘  ║ │
│                                                                    ╚═══════════════════════════════════╝ │
│                                                                                                         │
│  ═══════════════════════════════════════════════════════════════════════════════════════════════════════  │
│                                         TRAFFIC FLOW LEGEND                                             │
│                                                                                                         │
│  [RED]  ══════ VOICE PATH (SIP TLS 5061 + SRTP UDP 16384-32767) ══════                                 │
│         Oracle SBC ──► Interconnect ──► GTP ──► Dialogflow CX ──► (return path) ──► Genesys Agent      │
│                                                                                                         │
│  [BLUE] ────── DATA PATH (HTTPS 443 via Private Service Connect) ──────                                │
│         Genesys ORS ──► Interconnect ──► Private Service Connect ──► Cloud Run MW ──► Firestore/BQ     │
│                                                                                                         │
│  ═══════════════════════════════════════════════════════════════════════════════════════════════════════  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---


## 4. Dedicated Interconnect Design

### 4.1 Physical Connection Summary

| # | Location | Facility | Role | Capacity | Carrier |
|---|----------|----------|------|----------|---------|
| 1 | Dallas, TX | Equinix DA7 | Primary (Dallas Metro) | 10 Gbps Dedicated | AT&T Dark Fiber |
| 2 | Dallas, TX | Equinix DA2 | Secondary (Dallas Metro) | 10 Gbps Dedicated | Verizon Dark Fiber |
| 3 | Phoenix, AZ | Equinix PH1 | Primary (Phoenix/DR) | 10 Gbps Dedicated | AT&T Dark Fiber |
| 4 | Phoenix, AZ | DataBank PHX1 | Secondary (Phoenix/DR) | 10 Gbps Dedicated | Verizon Dark Fiber |

> **Note:** Customer does not have colocation presence. Cross-connects are established from customer data centers to the nearest Equinix/DataBank facilities via carrier-provided dark fiber (AT&T and Verizon).

### 4.2 Redundancy Model (99.99% SLA)

To achieve the 99.99% SLA, the design implements:

- **Metro-level diversity:** Two interconnects per metro using different facilities (DA7/DA2 in Dallas, PH1/PHX1 in Phoenix)
- **Carrier diversity:** AT&T on primary paths, Verizon on secondary paths
- **Path diversity:** Different physical fiber routes between DC and interconnect facilities
- **Geographic diversity:** Two separate metros (Dallas + Phoenix) providing cross-region failover

```
Dallas DC ──── AT&T Dark Fiber ────── Equinix DA7 ──── GCP (us-south1)  [Primary]
Dallas DC ──── Verizon Dark Fiber ─── Equinix DA2 ──── GCP (us-south1)  [Secondary]
Phoenix DC ─── AT&T Dark Fiber ────── Equinix PH1 ──── GCP (us-central1) [DR Primary]
Phoenix DC ─── Verizon Dark Fiber ─── DataBank PHX1 ── GCP (us-central1) [DR Secondary]
```

### 4.3 VLAN Attachment Design

Each physical interconnect carries two VLAN attachments for traffic separation:

| VLAN Attachment | VLAN ID | Purpose | Bandwidth Allocation | Subnet |
|----------------|---------|---------|---------------------|--------|
| voice-vlan | 100 | SIP signaling + RTP media | 5 Gbps (reserved) | 169.254.100.0/29 |
| data-vlan | 200 | HTTPS API / middleware | 5 Gbps (reserved) | 169.254.200.0/29 |

### 4.4 Interconnect Configuration

```yaml
# GCP Dedicated Interconnect - Dallas Primary (Equinix DA7)
resource "google_compute_interconnect" "dallas_primary" {
  name                 = "interconnect-dallas-da7-primary"
  location             = "dal-zone1-2"  # Equinix DA7
  interconnect_type    = "DEDICATED"
  link_type            = "LINK_TYPE_ETHERNET_10G_LR"
  requested_link_count = 1
  admin_enabled        = true
}

# VLAN Attachment - Voice (Dallas Primary)
resource "google_compute_interconnect_attachment" "dallas_primary_voice" {
  name                     = "vlan-attach-dallas-primary-voice"
  interconnect             = google_compute_interconnect.dallas_primary.id
  router                   = google_compute_router.dallas_router.id
  region                   = "us-south1"
  type                     = "DEDICATED"
  vlan_tag8021q            = 100
  bandwidth                = "BPS_5G"
  candidate_subnets        = ["169.254.100.0/29"]
  admin_enabled            = true
}

# VLAN Attachment - Data (Dallas Primary)
resource "google_compute_interconnect_attachment" "dallas_primary_data" {
  name                     = "vlan-attach-dallas-primary-data"
  interconnect             = google_compute_interconnect.dallas_primary.id
  router                   = google_compute_router.dallas_router.id
  region                   = "us-south1"
  type                     = "DEDICATED"
  vlan_tag8021q            = 200
  bandwidth                = "BPS_5G"
  candidate_subnets        = ["169.254.200.0/29"]
  admin_enabled            = true
}
```

### 4.5 BGP Peering Parameters

| Parameter | Customer Side | Google Side |
|-----------|--------------|-------------|
| **ASN** | 64512 (Private) | 16550 |
| **Peer IP (Voice VLAN - DA7)** | 169.254.100.1/29 | 169.254.100.2/29 |
| **Peer IP (Data VLAN - DA7)** | 169.254.200.1/29 | 169.254.200.2/29 |
| **MD5 Auth** | Enabled | Enabled |
| **BFD** | Enabled (300ms detect) | Enabled |
| **Hold Timer** | 15 seconds | 15 seconds |
| **Keepalive** | 5 seconds | 5 seconds |

### 4.6 Encryption

Per customer requirements, **no encryption is applied on the interconnect links themselves**. The physical dedicated interconnect provides inherent security through dedicated fiber paths. However:

- SIP signaling uses TLS (port 5061) end-to-end
- RTP media uses SRTP for voice payload encryption
- HTTPS/TLS 1.3 for all data API traffic

---


## 5. BGP Routing Design

### 5.1 Cloud Router Configuration

```yaml
# Cloud Router - Dallas (us-south1)
resource "google_compute_router" "dallas_router" {
  name    = "cloud-router-us-south1"
  region  = "us-south1"
  network = google_compute_network.contact_center_vpc.id

  bgp {
    asn               = 16550
    advertise_mode    = "CUSTOM"
    advertised_groups = ["ALL_SUBNETS"]

    # Advertise GCP subnets to on-prem
    advertised_ip_ranges {
      range       = "10.100.0.0/24"  # voice-subnet
      description = "Voice subnet (GTP, SBC Proxy)"
    }
    advertised_ip_ranges {
      range       = "10.101.0.0/24"  # data-subnet
      description = "Data subnet (Cloud Run, Firestore)"
    }
    advertised_ip_ranges {
      range       = "10.102.0.0/24"  # ccai-subnet
      description = "CCAI subnet (Dialogflow, STT/TTS)"
    }
    advertised_ip_ranges {
      range       = "199.36.153.4/30"  # restricted.googleapis.com
      description = "Restricted Google APIs (Private Google Access)"
    }
  }
}

# Cloud Router - Phoenix/DR (us-central1)
resource "google_compute_router" "phoenix_router" {
  name    = "cloud-router-us-central1"
  region  = "us-central1"
  network = google_compute_network.contact_center_vpc.id

  bgp {
    asn               = 16550
    advertise_mode    = "CUSTOM"
    advertised_groups = ["ALL_SUBNETS"]

    advertised_ip_ranges {
      range       = "10.100.1.0/24"  # voice-subnet-dr
      description = "Voice subnet DR"
    }
    advertised_ip_ranges {
      range       = "10.101.1.0/24"  # data-subnet-dr
      description = "Data subnet DR"
    }
    advertised_ip_ranges {
      range       = "10.102.1.0/24"  # ccai-subnet-dr
      description = "CCAI subnet DR"
    }
    advertised_ip_ranges {
      range       = "199.36.153.4/30"
      description = "Restricted Google APIs"
    }
  }
}
```

### 5.2 On-Premises Route Advertisements (Customer → GCP)

| Prefix | Description | Advertised From |
|--------|-------------|-----------------|
| 10.10.0.0/24 | Dallas DC - SBC Network | Dallas (DA7, DA2) |
| 10.10.1.0/24 | Dallas DC - Genesys ORS/SIP | Dallas (DA7, DA2) |
| 10.10.2.0/24 | Dallas DC - Management | Dallas (DA7, DA2) |
| 10.20.0.0/24 | Phoenix DC - SBC Network | Phoenix (PH1, PHX1) |
| 10.20.1.0/24 | Phoenix DC - Genesys DR | Phoenix (PH1, PHX1) |
| 10.20.2.0/24 | Phoenix DC - Management | Phoenix (PH1, PHX1) |

### 5.3 Path Selection (MED / Local-Preference)

```
┌─────────────────────────────────────────────────────────────────┐
│                    BGP PATH SELECTION LOGIC                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  DALLAS DC → GCP (Normal Operation):                             │
│    Primary:   DA7 (MED=100, Local-Pref=200)                     │
│    Secondary: DA2 (MED=200, Local-Pref=100)                     │
│                                                                   │
│  PHOENIX DC → GCP (Normal Operation):                            │
│    Primary:   PH1 (MED=100, Local-Pref=200)                     │
│    Secondary: PHX1 (MED=200, Local-Pref=100)                    │
│                                                                   │
│  FAILOVER SCENARIO (Dallas Interconnect Total Failure):          │
│    Dallas traffic → WAN link → Phoenix DC → PH1 → GCP           │
│    (BGP routes withdrawn from DA7/DA2, next-best = Phoenix)      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Customer Router BGP Config (Dallas Primary - DA7):**

```
router bgp 64512
  neighbor 169.254.100.2 remote-as 16550
  neighbor 169.254.100.2 description GCP-Dallas-DA7-Voice
  neighbor 169.254.100.2 password <md5-key>
  neighbor 169.254.100.2 timers 5 15
  neighbor 169.254.100.2 bfd
  !
  address-family ipv4 unicast
    neighbor 169.254.100.2 activate
    neighbor 169.254.100.2 route-map GCP-DALLAS-PRIMARY-OUT out
    neighbor 169.254.100.2 route-map GCP-DALLAS-PRIMARY-IN in
    network 10.10.0.0 mask 255.255.255.0
    network 10.10.1.0 mask 255.255.255.0
  exit-address-family
!
route-map GCP-DALLAS-PRIMARY-OUT permit 10
  set metric 100
  set community 64512:100
!
route-map GCP-DALLAS-PRIMARY-IN permit 10
  set local-preference 200
```

### 5.4 Failover Behavior

| Scenario | Detection Method | Failover Time | Traffic Path |
|----------|-----------------|---------------|--------------|
| Single link failure (DA7) | BFD (300ms) | < 1 second | DA7 → DA2 (same metro) |
| Metro failure (all Dallas links) | BGP withdrawal | < 30 seconds | Dallas DC → WAN → Phoenix DC → PH1 → GCP |
| GCP region failure (us-south1) | BGP withdrawal | < 30 seconds | Via Phoenix interconnect to us-central1 |
| Carrier failure (AT&T) | BFD + BGP | < 5 seconds | AT&T links → Verizon links |

### 5.5 Voice vs Data Traffic Separation

Traffic separation is achieved through separate VLAN attachments with distinct BGP sessions:

- **Voice VLAN (100):** Carries only SIP (TCP 5061) and RTP (UDP 16384-32767) traffic. BGP session advertises voice-subnet prefixes only.
- **Data VLAN (200):** Carries HTTPS API traffic (TCP 443). BGP session advertises data-subnet and ccai-subnet prefixes.

This separation enables independent QoS policies, monitoring, and troubleshooting for voice vs. data flows.

---


## 6. GCP VPC Network Design

### 6.1 VPC Structure

```
VPC: contact-center-vpc (Custom Mode)
│
├── voice-subnet: 10.100.0.0/24 (us-south1)
│   ├── Google Telephony Platform (GTP) endpoints
│   ├── SBC proxy / session relay
│   └── SIP/RTP termination points
│
├── voice-subnet-dr: 10.100.1.0/24 (us-central1)
│   └── DR replica of voice services
│
├── data-subnet: 10.101.0.0/24 (us-south1)
│   ├── Cloud Run - Middleware API (serverless VPC connector)
│   ├── Firestore (via Private Service Connect)
│   └── Pub/Sub endpoints
│
├── data-subnet-dr: 10.101.1.0/24 (us-central1)
│   └── DR replica of data services
│
├── ccai-subnet: 10.102.0.0/24 (us-south1)
│   ├── Dialogflow CX (via Private Service Connect)
│   ├── Speech-to-Text (STT) endpoints
│   └── Text-to-Speech (TTS) endpoints
│
├── ccai-subnet-dr: 10.102.1.0/24 (us-central1)
│   └── DR replica of CCAI services
│
└── mgmt-subnet: 10.103.0.0/24 (us-south1)
    ├── Cloud Monitoring / Logging agents
    ├── Bastion host (IAP-tunneled)
    └── Network monitoring probes
```

### 6.2 VPC Configuration

```yaml
resource "google_compute_network" "contact_center_vpc" {
  name                    = "contact-center-vpc"
  auto_create_subnetworks = false
  routing_mode            = "GLOBAL"  # Required for cross-region failover
  mtu                     = 1500
}

# Voice Subnet - Primary (us-south1)
resource "google_compute_subnetwork" "voice_subnet" {
  name                     = "voice-subnet"
  ip_cidr_range            = "10.100.0.0/24"
  region                   = "us-south1"
  network                  = google_compute_network.contact_center_vpc.id
  private_ip_google_access = true
  
  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 1.0
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Voice Subnet - DR (us-central1)
resource "google_compute_subnetwork" "voice_subnet_dr" {
  name                     = "voice-subnet-dr"
  ip_cidr_range            = "10.100.1.0/24"
  region                   = "us-central1"
  network                  = google_compute_network.contact_center_vpc.id
  private_ip_google_access = true
}

# Data Subnet - Primary (us-south1)
resource "google_compute_subnetwork" "data_subnet" {
  name                     = "data-subnet"
  ip_cidr_range            = "10.101.0.0/24"
  region                   = "us-south1"
  network                  = google_compute_network.contact_center_vpc.id
  private_ip_google_access = true
}

# Data Subnet - DR (us-central1)
resource "google_compute_subnetwork" "data_subnet_dr" {
  name                     = "data-subnet-dr"
  ip_cidr_range            = "10.101.1.0/24"
  region                   = "us-central1"
  network                  = google_compute_network.contact_center_vpc.id
  private_ip_google_access = true
}

# CCAI Subnet - Primary (us-south1)
resource "google_compute_subnetwork" "ccai_subnet" {
  name                     = "ccai-subnet"
  ip_cidr_range            = "10.102.0.0/24"
  region                   = "us-south1"
  network                  = google_compute_network.contact_center_vpc.id
  private_ip_google_access = true
}

# CCAI Subnet - DR (us-central1)
resource "google_compute_subnetwork" "ccai_subnet_dr" {
  name                     = "ccai-subnet-dr"
  ip_cidr_range            = "10.102.1.0/24"
  region                   = "us-central1"
  network                  = google_compute_network.contact_center_vpc.id
  private_ip_google_access = true
}

# Management Subnet (us-south1)
resource "google_compute_subnetwork" "mgmt_subnet" {
  name                     = "mgmt-subnet"
  ip_cidr_range            = "10.103.0.0/24"
  region                   = "us-south1"
  network                  = google_compute_network.contact_center_vpc.id
  private_ip_google_access = true
}
```

### 6.3 Private Service Connect (PSC) Endpoints

```yaml
# Private Service Connect - Cloud Run Middleware
resource "google_compute_global_address" "psc_cloud_run" {
  name         = "psc-cloud-run-middleware"
  purpose      = "PRIVATE_SERVICE_CONNECT"
  address_type = "INTERNAL"
  address      = "10.101.0.100"
  network      = google_compute_network.contact_center_vpc.id
}

# Private Service Connect - Dialogflow CX
resource "google_compute_global_address" "psc_dialogflow" {
  name         = "psc-dialogflow-cx"
  purpose      = "PRIVATE_SERVICE_CONNECT"
  address_type = "INTERNAL"
  address      = "10.102.0.100"
  network      = google_compute_network.contact_center_vpc.id
}
```

### 6.4 DNS Configuration

```yaml
# Private DNS zone for googleapis.com (route to restricted VIPs)
resource "google_dns_managed_zone" "googleapis_private" {
  name        = "googleapis-private"
  dns_name    = "googleapis.com."
  visibility  = "private"
  
  private_visibility_config {
    networks {
      network_url = google_compute_network.contact_center_vpc.id
    }
  }
}

# A record pointing to restricted.googleapis.com VIPs
resource "google_dns_record_set" "restricted_googleapis" {
  name         = "restricted.googleapis.com."
  type         = "A"
  ttl          = 300
  managed_zone = google_dns_managed_zone.googleapis_private.name
  rrdatas      = ["199.36.153.4", "199.36.153.5", "199.36.153.6", "199.36.153.7"]
}

# CNAME for all Google API services
resource "google_dns_record_set" "wildcard_googleapis" {
  name         = "*.googleapis.com."
  type         = "CNAME"
  ttl          = 300
  managed_zone = google_dns_managed_zone.googleapis_private.name
  rrdatas      = ["restricted.googleapis.com."]
}
```

---


## 7. Voice Path Architecture

### 7.1 Complete Voice Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        VOICE PATH - DETAILED FLOW                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  STEP 1: Inbound Call Arrives                                                   │
│  ┌──────┐      ┌─────────────────────────────┐                                  │
│  │ PSTN │─────►│ Oracle SBC (Dallas DC)      │                                  │
│  │      │ SIP  │ - Ingress normalization      │                                  │
│  └──────┘      │ - Codec negotiation (G.711u) │                                  │
│                │ - Call routing decision       │                                  │
│                └──────────────┬────────────────┘                                 │
│                               │                                                  │
│  STEP 2: SBC → GCP (via Dedicated Interconnect)                                │
│                               │ SIP TLS (5061) + SRTP                           │
│                               ▼                                                  │
│           ┌───────────────────────────────────────────┐                          │
│           │  GCP Dedicated Interconnect (voice-vlan)  │                          │
│           │  Equinix DA7 → us-south1                  │                          │
│           │  Latency: 1-2ms                           │                          │
│           └───────────────────┬───────────────────────┘                          │
│                               │                                                  │
│  STEP 3: Google Telephony Platform (GTP) → Dialogflow CX                       │
│                               ▼                                                  │
│           ┌───────────────────────────────────────────┐                          │
│           │  Google Telephony Platform (GTP)          │                          │
│           │  telephony.googleapis.com                 │                          │
│           │  - SIP trunk termination                  │                          │
│           │  - Media relay (RTP ↔ internal)          │                          │
│           └───────────────────┬───────────────────────┘                          │
│                               │                                                  │
│                               ▼                                                  │
│           ┌───────────────────────────────────────────┐                          │
│           │  Dialogflow CX Virtual Agent              │                          │
│           │  - Speech-to-Text (streaming)             │                          │
│           │  - NLU intent matching                    │                          │
│           │  - Text-to-Speech (response)              │                          │
│           │  - CCAI Insights (real-time)              │                          │
│           │  Processing latency: 50-100ms             │                          │
│           └───────────────────┬───────────────────────┘                          │
│                               │                                                  │
│  STEP 4: Agent Transfer (if needed)                                             │
│                               │ Dialogflow determines live agent needed          │
│                               ▼                                                  │
│           ┌───────────────────────────────────────────┐                          │
│           │  GTP → Interconnect → Oracle SBC          │                          │
│           │  SIP REFER / re-INVITE back to on-prem    │                          │
│           └───────────────────┬───────────────────────┘                          │
│                               │                                                  │
│                               ▼                                                  │
│           ┌───────────────────────────────────────────┐                          │
│           │  Genesys SIP Server → Agent Desktop       │                          │
│           │  - Agent handles call with CCAI Assist    │                          │
│           │  - Real-time transcription continues      │                          │
│           └───────────────────────────────────────────┘                          │
│                                                                                  │
│  STEP 5: Media (RTP) Path During Agent-Assisted Call                            │
│  ┌──────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     │
│  │Caller│◄───►│Oracle   │◄───►│  GCP    │◄───►│Oracle   │◄───►│Genesys  │     │
│  │(PSTN)│ RTP │SBC      │SRTP │ CCAI    │SRTP │SBC      │ RTP │Agent    │     │
│  └──────┘     └─────────┘     │(process)│     └─────────┘     └─────────┘     │
│                                │audio    │                                       │
│                                └─────────┘                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 SIP Signaling Path

| Segment | Protocol | Port | Encryption | Notes |
|---------|----------|------|------------|-------|
| PSTN → Oracle SBC | SIP/UDP or TCP | 5060 | None (carrier trunk) | Inbound from carrier |
| Oracle SBC → GTP | SIP/TLS | 5061 | TLS 1.2+ | Via Dedicated Interconnect |
| GTP → Dialogflow CX | Internal gRPC | N/A | Internal GCP encryption | Google-internal |
| GTP → Oracle SBC (return) | SIP/TLS | 5061 | TLS 1.2+ | Agent transfer |
| Oracle SBC → Genesys SIP | SIP/TCP | 5060 | None (LAN) | Internal DC network |

### 7.3 RTP Media Path

| Segment | Protocol | Port Range | Codec | Bitrate |
|---------|----------|-----------|-------|---------|
| PSTN → Oracle SBC | RTP | Dynamic | G.711u | 64 Kbps + overhead = 87 Kbps |
| Oracle SBC → GTP | SRTP | 16384-32767 | G.711u | 87 Kbps |
| GTP → CCAI (STT) | Internal stream | N/A | Linear16 | Converted internally |
| GTP → Oracle SBC (return) | SRTP | 16384-32767 | G.711u | 87 Kbps |
| Oracle SBC → Genesys Agent | RTP | 16384-32767 | G.711u | 87 Kbps |

> **Codec Requirement:** G.711u (μ-law) is **required** for optimal CCAI Speech-to-Text quality. Do not use compressed codecs (G.729, Opus) on the SBC-to-GCP path as they degrade STT accuracy.

### 7.4 GTP SIP Trunk Configuration

```yaml
# Dialogflow CX SIP Trunk Configuration
SIP Trunk:
  Name: "onprem-oracle-sbc-trunk"
  Endpoint: telephony.googleapis.com
  Transport: TLS (port 5061)
  
  SBC Configuration:
    Remote SIP URI: sip:telephony.googleapis.com:5061;transport=tls
    Codec Priority:
      1. G.711u (PCMU) - REQUIRED
      2. G.711a (PCMA) - fallback
    DTMF Mode: RFC 2833 (in-band)
    Session Timers: Enabled (1800s)
    Max Sessions: 100 (concurrent)
    
  Media:
    SRTP: Required (AES_CM_128_HMAC_SHA1_80)
    RTP Port Range: 16384-32767
    Ptime: 20ms
    ICE: Disabled (direct media path via interconnect)
```

### 7.5 Latency Budget (Voice Path)

| Segment | Expected Latency | Notes |
|---------|-----------------|-------|
| Dallas DC → Equinix DA7 (dark fiber) | < 1 ms | ~5 km fiber run |
| Equinix DA7 → GCP us-south1 (interconnect) | 1-2 ms | Dedicated 10G link |
| GCP internal network (to GTP) | 1-2 ms | Intra-region |
| GTP → Dialogflow CX (STT processing) | 50-100 ms | Streaming STT + NLU |
| Return path (GCP → Interconnect → SBC) | 3-5 ms | Reverse of above |
| **Total one-way (caller to CCAI response)** | **~60-80 ms** | **Within target** |

> **Latency Target Met:** The total one-way voice path latency of 60-80ms is within the < 80ms requirement. The dominant contributor is CCAI/Dialogflow CX processing time (50-100ms), which is an application-layer latency that cannot be reduced through network optimization.

---


## 8. Data Path Architecture

### 8.1 Real-Time Middleware Integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA PATH - MIDDLEWARE INTEGRATION                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────┐         ┌──────────────────────────────────────┐   │
│  │  Genesys ORS        │         │  GCP (us-south1) - data-subnet       │   │
│  │  (Dallas DC)        │         │                                      │   │
│  │                     │  HTTPS  │  ┌──────────────────────────────┐    │   │
│  │  Call routing logic  │────────►│  │  Private Service Connect     │    │   │
│  │  "Which agent?"     │   443   │  │  Endpoint: 10.101.0.100      │    │   │
│  │  "What context?"    │◄────────│  │           │                  │    │   │
│  │                     │         │  │           ▼                  │    │   │
│  └─────────────────────┘         │  │  ┌────────────────────┐     │    │   │
│         │                        │  │  │  Cloud Run          │     │    │   │
│         │ Via Dedicated          │  │  │  Middleware API     │     │    │   │
│         │ Interconnect           │  │  │  - Customer lookup  │     │    │   │
│         │ (data-vlan)            │  │  │  - Context enrich   │     │    │   │
│         │                        │  │  │  - Routing rules    │     │    │   │
│         │                        │  │  └────────┬───────────┘     │    │   │
│         │                        │  │           │                  │    │   │
│         │                        │  │     ┌─────┴─────┐           │    │   │
│         │                        │  │     │           │           │    │   │
│         │                        │  │     ▼           ▼           │    │   │
│         │                        │  │  ┌───────┐  ┌─────────┐    │    │   │
│         │                        │  │  │Firestoe│  │BigQuery │    │    │   │
│         │                        │  │  │(NoSQL) │  │(Anlytcs)│    │    │   │
│         │                        │  │  └───────┘  └─────────┘    │    │   │
│         │                        │  └──────────────────────────────┘    │   │
│         │                        └──────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Data Flow Details

**Request Flow (during call routing):**

1. Genesys ORS receives inbound call event
2. ORS routing strategy triggers external API call to GCP middleware
3. Traffic exits Dallas DC via data-vlan on Dedicated Interconnect
4. Enters GCP VPC via Cloud Router → data-subnet
5. Hits Private Service Connect endpoint (10.101.0.100)
6. Cloud Run middleware processes request:
   - Queries Firestore for customer profile/context
   - Applies business routing rules
   - Returns routing decision + context to ORS
7. Response returns via same path (< 50ms round-trip)

### 8.3 Private Service Connect Configuration

```yaml
# Cloud Run Service (Middleware API)
resource "google_cloud_run_v2_service" "middleware_api" {
  name     = "contact-center-middleware"
  location = "us-south1"
  
  template {
    vpc_access {
      connector = google_vpc_access_connector.data_connector.id
      egress    = "ALL_TRAFFIC"
    }
    
    containers {
      image = "us-south1-docker.pkg.dev/project-id/middleware/api:latest"
      
      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }
    }
    
    scaling {
      min_instance_count = 2   # Always warm for low latency
      max_instance_count = 10
    }
  }
  
  ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"  # No public access
}

# VPC Access Connector
resource "google_vpc_access_connector" "data_connector" {
  name          = "data-subnet-connector"
  region        = "us-south1"
  network       = google_compute_network.contact_center_vpc.id
  ip_cidr_range = "10.101.0.48/28"  # Connector range within data-subnet
  
  min_instances = 2
  max_instances = 10
}
```

### 8.4 Private Google Access

All GCP API access (Firestore, BigQuery, Pub/Sub, Cloud Logging) routes through Private Google Access via the restricted.googleapis.com VIP range (199.36.153.4/30), advertised to on-prem via BGP:

- **No public IP addresses** are assigned to any GCP resources
- **All Google API traffic** resolves to restricted VIPs via private DNS
- **On-prem access** to GCP APIs routes through the Dedicated Interconnect to restricted VIPs

---


## 9. Five9 Connectivity

### 9.1 Architecture Overview

Five9 serves as the IVR front-end for certain call flows. The Oracle SBC acts as the **demarcation point** between external Five9 traffic and internal private GCP traffic.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FIVE9 CONNECTIVITY MODEL                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐                    ┌─────────────────────────────────────┐  │
│  │  Five9      │                    │  Dallas Data Center                 │  │
│  │  Cloud      │                    │                                     │  │
│  │             │  Option A:         │  ┌───────────────────────────────┐  │  │
│  │  IVR        │  TLS/SRTP over     │  │  Oracle SBC (Demarcation)    │  │  │
│  │  Platform   │──Internet──────────┼─►│                               │  │  │
│  │             │                    │  │  External-facing: Five9       │  │  │
│  │             │  Option B:         │  │  Internal-facing: GCP + LAN  │  │  │
│  │             │──Equinix Fabric────┼─►│                               │  │  │
│  │             │  (Private peering) │  └──────────┬──────────┬─────────┘  │  │
│  └─────────────┘                    │             │          │            │  │
│                                     │             │          │            │  │
│                                     │             ▼          ▼            │  │
│                                     │  ┌──────────────┐ ┌────────────┐   │  │
│                                     │  │ GCP (via     │ │ Genesys    │   │  │
│                                     │  │ Interconnect)│ │ (on LAN)   │   │  │
│                                     │  └──────────────┘ └────────────┘   │  │
│                                     └─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Five9 Call Flow Scenarios

**Scenario A: Five9 → GCP CCAI (for AI treatment)**

```
Five9 IVR → (Internet/TLS) → Oracle SBC → (Dedicated Interconnect) → GCP GTP → Dialogflow CX
```

- Five9 handles initial IVR menu
- If CCAI virtual agent treatment needed, Five9 transfers call to SBC
- SBC routes to GCP via private interconnect
- Dialogflow CX provides virtual agent experience

**Scenario B: Five9 → Genesys Agent (direct to agent)**

```
Five9 IVR → (Internet/TLS) → Oracle SBC → (LAN) → Genesys SIP Server → Agent
```

- Five9 handles IVR, determines agent needed
- Transfers to SBC, which routes to Genesys on LAN
- No GCP involvement — stays entirely on-premises

**Scenario C: Five9 → GCP CCAI → Genesys Agent (AI then agent)**

```
Five9 → SBC → Interconnect → GCP CCAI → (agent needed) → Interconnect → SBC → Genesys Agent
```

- Combined flow: Five9 IVR front-end, CCAI virtual agent, then live agent escalation

### 9.3 Five9 SBC Configuration

```yaml
# Oracle SBC - Five9 Realm Configuration
SBC Five9 Realm:
  Name: "five9-external"
  Interface: External (Internet-facing)
  Transport: TLS 1.2+
  Port: 5061
  
  Allowed Peers:
    - Five9 SIP Proxy IPs (provided by Five9)
    - TLS Certificate: Five9 CA-signed cert
  
  Codec Policy:
    - G.711u (preferred)
    - G.729 (acceptable from Five9, transcoded to G.711u for GCP)
  
  Media Security:
    - SRTP required (from Five9)
    - RTP allowed (to Genesys LAN only)
  
  Session Capacity: 200 concurrent (Five9 sessions)
  
  Routing Rules:
    - If destination = CCAI → route to GCP realm (via interconnect)
    - If destination = Agent → route to Genesys realm (LAN)
```

### 9.4 Security Considerations

| Aspect | Five9 → SBC | SBC → GCP |
|--------|-------------|-----------|
| **Network** | Public Internet (encrypted) | Dedicated Interconnect (private) |
| **Transport** | TLS 1.2+ | TLS 1.2+ (within private network) |
| **Media** | SRTP (mandatory) | SRTP (mandatory) |
| **Access Control** | IP whitelist + TLS cert | Private network (no public exposure) |
| **DDoS Protection** | SBC rate limiting + carrier filtering | N/A (private) |

> **Key Design Decision:** The Oracle SBC provides a clear security boundary. Five9 traffic never touches GCP directly — it must traverse the SBC, which enforces security policies, codec normalization, and access control before any traffic enters the private interconnect path.

---


## 10. VPC Service Controls

### 10.1 Service Perimeter Design

VPC Service Controls create a security perimeter around sensitive GCP services, preventing data exfiltration and unauthorized access even from within GCP.

```yaml
# VPC Service Controls Perimeter
resource "google_access_context_manager_service_perimeter" "ccai_perimeter" {
  parent = "accessPolicies/${var.access_policy_id}"
  name   = "accessPolicies/${var.access_policy_id}/servicePerimeters/ccai_contact_center"
  title  = "CCAI Contact Center Perimeter"

  status {
    # Protected Services
    restricted_services = [
      "run.googleapis.com",           # Cloud Run (middleware)
      "firestore.googleapis.com",      # Firestore (customer data)
      "dialogflow.googleapis.com",     # Dialogflow CX
      "bigquery.googleapis.com",       # BigQuery (analytics)
      "speech.googleapis.com",         # Speech-to-Text
      "texttospeech.googleapis.com",   # Text-to-Speech
      "pubsub.googleapis.com",         # Pub/Sub (event streaming)
      "storage.googleapis.com",        # Cloud Storage (recordings)
    ]

    # Resources inside perimeter
    resources = [
      "projects/${var.project_number}"
    ]

    # Access Levels (who can reach services inside the perimeter)
    access_levels = [
      "accessPolicies/${var.access_policy_id}/accessLevels/onprem_interconnect",
      "accessPolicies/${var.access_policy_id}/accessLevels/gcp_service_accounts",
    ]

    # VPC accessible services
    vpc_accessible_services {
      enable_restriction = true
      allowed_services   = [
        "run.googleapis.com",
        "firestore.googleapis.com",
        "dialogflow.googleapis.com",
        "speech.googleapis.com",
        "texttospeech.googleapis.com",
      ]
    }
  }
}
```

### 10.2 Access Levels

```yaml
# Access Level: On-Premises via Interconnect
resource "google_access_context_manager_access_level" "onprem_interconnect" {
  parent = "accessPolicies/${var.access_policy_id}"
  name   = "accessPolicies/${var.access_policy_id}/accessLevels/onprem_interconnect"
  title  = "On-Premises via Dedicated Interconnect"

  basic {
    conditions {
      # On-prem IP ranges that access GCP via interconnect
      ip_subnetworks = [
        "10.10.0.0/24",   # Dallas DC - SBC Network
        "10.10.1.0/24",   # Dallas DC - Genesys ORS/SIP
        "10.10.2.0/24",   # Dallas DC - Management
        "10.20.0.0/24",   # Phoenix DC - SBC Network
        "10.20.1.0/24",   # Phoenix DC - Genesys DR
        "10.20.2.0/24",   # Phoenix DC - Management
      ]
    }
  }
}

# Access Level: GCP Service Accounts
resource "google_access_context_manager_access_level" "gcp_service_accounts" {
  parent = "accessPolicies/${var.access_policy_id}"
  name   = "accessPolicies/${var.access_policy_id}/accessLevels/gcp_service_accounts"
  title  = "Authorized GCP Service Accounts"

  basic {
    conditions {
      members = [
        "serviceAccount:middleware-api@${var.project_id}.iam.gserviceaccount.com",
        "serviceAccount:dialogflow-cx@${var.project_id}.iam.gserviceaccount.com",
        "serviceAccount:ccai-pipeline@${var.project_id}.iam.gserviceaccount.com",
      ]
    }
  }
}
```

### 10.3 Ingress / Egress Policies

```yaml
# Ingress Policy: Allow on-prem to call Cloud Run middleware
ingress_policies {
  ingress_from {
    sources {
      access_level = "accessPolicies/${var.access_policy_id}/accessLevels/onprem_interconnect"
    }
    identity_type = "ANY_IDENTITY"
  }
  ingress_to {
    resources = ["projects/${var.project_number}"]
    operations {
      service_name = "run.googleapis.com"
      method_selectors {
        method = "*"
      }
    }
  }
}

# Ingress Policy: Allow GTP to access Dialogflow
ingress_policies {
  ingress_from {
    sources {
      resource = "projects/${var.gtp_project_number}"  # Google Telephony Platform project
    }
    identity_type = "ANY_SERVICE_ACCOUNT"
  }
  ingress_to {
    resources = ["projects/${var.project_number}"]
    operations {
      service_name = "dialogflow.googleapis.com"
      method_selectors {
        method = "*"
      }
    }
  }
}

# Egress Policy: Allow middleware to write to BigQuery (analytics)
egress_policies {
  egress_from {
    identities = [
      "serviceAccount:middleware-api@${var.project_id}.iam.gserviceaccount.com"
    ]
  }
  egress_to {
    resources = ["projects/${var.project_number}"]
    operations {
      service_name = "bigquery.googleapis.com"
      method_selectors {
        method = "*"
      }
    }
  }
}
```

---


## 11. Firewall Rules

### 11.1 GCP VPC Firewall Rules

| Priority | Name | Direction | Source | Destination | Protocol/Ports | Action | Description |
|----------|------|-----------|--------|-------------|----------------|--------|-------------|
| 100 | `allow-sip-from-onprem` | INGRESS | 10.10.0.0/24, 10.20.0.0/24 | voice-subnet (10.100.0.0/24) | TCP/5061 | ALLOW | SIP TLS signaling from on-prem SBC |
| 110 | `allow-rtp-from-onprem` | INGRESS | 10.10.0.0/24, 10.20.0.0/24 | voice-subnet (10.100.0.0/24) | UDP/16384-32767 | ALLOW | SRTP media from on-prem SBC |
| 120 | `allow-https-from-onprem` | INGRESS | 10.10.1.0/24, 10.20.1.0/24 | data-subnet (10.101.0.0/24) | TCP/443 | ALLOW | HTTPS API calls from Genesys ORS |
| 200 | `allow-voice-to-ccai` | INGRESS | voice-subnet (10.100.0.0/24) | ccai-subnet (10.102.0.0/24) | TCP/443 | ALLOW | GTP to Dialogflow CX (internal) |
| 210 | `allow-data-to-ccai` | INGRESS | data-subnet (10.101.0.0/24) | ccai-subnet (10.102.0.0/24) | TCP/443 | ALLOW | Cloud Run to CCAI services |
| 220 | `allow-data-to-firestore` | INGRESS | data-subnet (10.101.0.0/24) | 199.36.153.4/30 | TCP/443 | ALLOW | Middleware to Firestore via restricted VIP |
| 300 | `allow-mgmt-ssh-iap` | INGRESS | 35.235.240.0/20 (IAP range) | mgmt-subnet (10.103.0.0/24) | TCP/22 | ALLOW | IAP-tunneled SSH to bastion |
| 310 | `allow-mgmt-to-all` | INGRESS | mgmt-subnet (10.103.0.0/24) | All subnets | TCP/22,443; ICMP | ALLOW | Management access for monitoring |
| 900 | `allow-health-checks` | INGRESS | 35.191.0.0/16, 130.211.0.0/22 | All subnets | TCP/443 | ALLOW | GCP health check probes |
| 1000 | `allow-internal-vpc` | INGRESS | 10.100.0.0/22 | 10.100.0.0/22 | All | ALLOW | Intra-VPC communication |
| 65534 | `deny-all-ingress` | INGRESS | 0.0.0.0/0 | All | All | DENY | Default deny all (implicit) |
| 65534 | `deny-all-egress` | EGRESS | All | 0.0.0.0/0 | All | DENY | Default deny all egress |
| 100 | `allow-egress-restricted-apis` | EGRESS | All subnets | 199.36.153.4/30 | TCP/443 | ALLOW | Egress to restricted.googleapis.com |
| 110 | `allow-egress-to-onprem` | EGRESS | voice-subnet, data-subnet | 10.10.0.0/16, 10.20.0.0/16 | TCP/5061; UDP/16384-32767; TCP/443 | ALLOW | Return traffic to on-prem |

### 11.2 Firewall Rule Implementation

```yaml
# Allow SIP TLS from on-prem SBC to voice subnet
resource "google_compute_firewall" "allow_sip_from_onprem" {
  name    = "allow-sip-from-onprem"
  network = google_compute_network.contact_center_vpc.id
  
  priority  = 100
  direction = "INGRESS"
  
  allow {
    protocol = "tcp"
    ports    = ["5061"]
  }
  
  source_ranges = [
    "10.10.0.0/24",  # Dallas DC SBC network
    "10.20.0.0/24",  # Phoenix DC SBC network
  ]
  
  target_tags = ["voice-endpoint"]
  
  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

# Allow SRTP from on-prem SBC to voice subnet
resource "google_compute_firewall" "allow_rtp_from_onprem" {
  name    = "allow-rtp-from-onprem"
  network = google_compute_network.contact_center_vpc.id
  
  priority  = 110
  direction = "INGRESS"
  
  allow {
    protocol = "udp"
    ports    = ["16384-32767"]
  }
  
  source_ranges = [
    "10.10.0.0/24",
    "10.20.0.0/24",
  ]
  
  target_tags = ["voice-endpoint"]
}

# Allow HTTPS from Genesys ORS to data subnet
resource "google_compute_firewall" "allow_https_from_onprem" {
  name    = "allow-https-from-onprem"
  network = google_compute_network.contact_center_vpc.id
  
  priority  = 120
  direction = "INGRESS"
  
  allow {
    protocol = "tcp"
    ports    = ["443"]
  }
  
  source_ranges = [
    "10.10.1.0/24",  # Dallas DC Genesys network
    "10.20.1.0/24",  # Phoenix DC Genesys network
  ]
  
  target_tags = ["data-endpoint"]
}

# Default deny all ingress (explicit for visibility)
resource "google_compute_firewall" "deny_all_ingress" {
  name    = "deny-all-ingress"
  network = google_compute_network.contact_center_vpc.id
  
  priority  = 65534
  direction = "INGRESS"
  
  deny {
    protocol = "all"
  }
  
  source_ranges = ["0.0.0.0/0"]
}
```

### 11.3 On-Premises Firewall Rules (Customer Responsibility)

| Source | Destination | Protocol/Port | Purpose |
|--------|-------------|---------------|---------|
| Oracle SBC | GCP voice-subnet (10.100.0.0/24) | TCP/5061 | SIP TLS to GTP |
| Oracle SBC | GCP voice-subnet (10.100.0.0/24) | UDP/16384-32767 | SRTP media to GTP |
| Genesys ORS | GCP data-subnet (10.101.0.0/24) | TCP/443 | HTTPS to Cloud Run middleware |
| Management | GCP mgmt-subnet (10.103.0.0/24) | TCP/22, ICMP | Monitoring/troubleshooting |
| Five9 IPs (whitelist) | Oracle SBC external interface | TCP/5061, UDP/16384-32767 | Five9 SIP/RTP |

---


## 12. Bandwidth Calculation

### 12.1 Voice Traffic

| Parameter | Value | Notes |
|-----------|-------|-------|
| Daily call volume | 10,000 calls/day | Business hours weighted |
| Peak concurrent calls | ~50 calls | Estimated from Erlang B model |
| Codec | G.711u (μ-law) | Required for CCAI STT quality |
| Payload per call | 64 Kbps | G.711 raw payload |
| RTP overhead (IP/UDP/RTP headers) | 23 Kbps | 40 bytes per 20ms frame |
| **Total per call** | **87 Kbps** | Payload + overhead |
| **Peak bandwidth (50 calls)** | **4.35 Mbps** | 50 × 87 Kbps |
| Burst allowance (2x peak) | 8.7 Mbps | Handling spikes |

### 12.2 Data Traffic (Middleware API)

| Parameter | Value | Notes |
|-----------|-------|-------|
| API call rate | 7 calls/minute | Genesys ORS → Cloud Run |
| Average request payload | ~2 KB | JSON request body |
| Average response payload | ~3 KB | JSON response with context |
| **Sustained bandwidth** | **~0.6 Kbps** | Negligible |
| Peak burst (100 calls/min) | ~7 Kbps | Still negligible |

### 12.3 Total Bandwidth Summary

```
┌─────────────────────────────────────────────────────────────────┐
│               BANDWIDTH UTILIZATION SUMMARY                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Voice (peak):           4.35 Mbps    ████░░░░░░░░░░░░░  0.04%  │
│  Voice (burst):          8.70 Mbps    ████████░░░░░░░░░  0.09%  │
│  Data (sustained):       0.001 Mbps   ░░░░░░░░░░░░░░░░░  ~0%   │
│  Data (burst):           0.007 Mbps   ░░░░░░░░░░░░░░░░░  ~0%   │
│  ─────────────────────────────────────────────────────────────── │
│  TOTAL SUSTAINED:        < 10 Mbps    ████░░░░░░░░░░░░░  0.1%  │
│  TOTAL BURST:            < 50 Mbps    ████████████░░░░░  0.5%  │
│                                                                   │
│  Interconnect Capacity:  10,000 Mbps (10 Gbps per link)          │
│  Utilization:            < 0.5% (massively over-provisioned)     │
│                                                                   │
│  RATIONALE: 10 Gbps selected for:                                │
│    • Minimum Dedicated Interconnect port speed                   │
│    • Future-proofing for full contact center migration            │
│    • Additional workload migration (analytics, recording, etc.)  │
│    • 99.99% SLA requirement (requires Dedicated, not Partner)    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 12.4 Interconnect Egress Cost Projection

| Traffic Type | Monthly Volume | Egress Rate | Monthly Cost |
|-------------|---------------|-------------|--------------|
| Voice (RTP) | ~150 GB | $0.02/GB | ~$3.00 |
| Data (API) | < 1 GB | $0.02/GB | ~$0.02 |
| **Total Egress** | **~151 GB** | | **~$3.02** |

> **Note:** Interconnect egress pricing ($0.02/GB) is significantly lower than standard internet egress ($0.08-0.12/GB). The dedicated interconnect provides both privacy and cost advantages.

---


## 13. High Availability & DR

### 13.1 HA Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HIGH AVAILABILITY DESIGN                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LAYER 1: SBC High Availability                                             │
│  ┌─────────────────────────────────────────────────────────┐                │
│  │  Oracle SBC HA Pair (Active/Standby with VRRP)          │                │
│  │                                                         │                │
│  │  SBC-1 (Active)  ←── VRRP ──→  SBC-2 (Standby)       │                │
│  │  VIP: 10.10.0.10              VIP: 10.10.0.11         │                │
│  │  Both connected to BOTH interconnect paths              │                │
│  │  Failover: < 3 seconds                                 │                │
│  └─────────────────────────────────────────────────────────┘                │
│                                                                              │
│  LAYER 2: Interconnect Redundancy (per metro)                               │
│  ┌─────────────────────────────────────────────────────────┐                │
│  │  Path A: AT&T → Equinix DA7 → GCP (Primary)            │                │
│  │  Path B: Verizon → Equinix DA2 → GCP (Secondary)       │                │
│  │                                                         │                │
│  │  BFD detection: 300ms                                   │                │
│  │  BGP convergence: < 5 seconds (within metro)            │                │
│  └─────────────────────────────────────────────────────────┘                │
│                                                                              │
│  LAYER 3: Geographic Redundancy (cross-metro)                               │
│  ┌─────────────────────────────────────────────────────────┐                │
│  │  Dallas (Primary) ←── WAN link ──→ Phoenix (DR)         │                │
│  │                                                         │                │
│  │  If ALL Dallas interconnects fail:                      │                │
│  │    → BGP withdraws Dallas routes                        │                │
│  │    → Traffic routes via WAN to Phoenix DC               │                │
│  │    → Phoenix interconnects reach GCP us-central1        │                │
│  │    → Failover time: < 30 seconds (BGP convergence)     │                │
│  └─────────────────────────────────────────────────────────┘                │
│                                                                              │
│  LAYER 4: GCP Region Redundancy                                             │
│  ┌─────────────────────────────────────────────────────────┐                │
│  │  us-south1 (Primary) ←── Global VPC ──→ us-central1   │                │
│  │                                                         │                │
│  │  If GCP us-south1 has regional failure:                 │                │
│  │    → Cloud Router withdraws us-south1 prefixes          │                │
│  │    → On-prem routes shift to us-central1 prefixes       │                │
│  │    → DR Dialogflow CX agent takes over                  │                │
│  │    → Cloud Run DR instance serves middleware            │                │
│  └─────────────────────────────────────────────────────────┘                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Failure Scenarios and Recovery

| # | Failure Scenario | Detection | Recovery Action | RTO |
|---|-----------------|-----------|-----------------|-----|
| 1 | Single SBC failure | VRRP heartbeat | Standby SBC assumes VIP | < 3 sec |
| 2 | Single interconnect link (DA7) | BFD (300ms) | Traffic shifts to DA2 | < 1 sec |
| 3 | Single carrier failure (AT&T) | BFD + BGP | All traffic to Verizon links | < 5 sec |
| 4 | Complete Dallas metro failure | BGP route withdrawal | Route via Phoenix DC → us-central1 | < 30 sec |
| 5 | GCP us-south1 region failure | BGP route withdrawal | Failover to us-central1 DR | < 30 sec |
| 6 | Genesys on-prem failure (Dallas) | Application monitoring | Activate Phoenix DR Genesys | Minutes (application) |
| 7 | Dialogflow CX service degradation | Health checks | Redirect to backup flow / IVR | Application-dependent |

### 13.3 SBC High Availability Configuration

```yaml
# Oracle SBC HA Configuration
SBC HA Cluster:
  Mode: Active/Standby
  Protocol: VRRP (Virtual Router Redundancy Protocol)
  
  SBC-Primary:
    Hostname: sbc-dal-01
    Physical IP: 10.10.0.11
    VRRP Priority: 200
    Interconnect Paths: DA7 (VLAN 100, 200), DA2 (VLAN 100, 200)
    
  SBC-Standby:
    Hostname: sbc-dal-02
    Physical IP: 10.10.0.12
    VRRP Priority: 100
    Interconnect Paths: DA7 (VLAN 100, 200), DA2 (VLAN 100, 200)
    
  Virtual IPs:
    - 10.10.0.10 (SIP signaling VIP)
    - 10.10.0.13 (Media/RTP VIP)
    
  Health Checks:
    - VRRP advertisement: 1 second
    - Hold time: 3 seconds
    - Track interfaces: all interconnect-facing ports
    - Track BGP sessions: if BGP down → decrement priority
```

### 13.4 DR Activation Procedure

```
DR ACTIVATION RUNBOOK (Summary):

1. AUTOMATIC (Network Layer):
   - BFD/BGP detects interconnect failure → automatic failover (< 30 sec)
   - No manual intervention required for network path switching

2. SEMI-AUTOMATIC (Application Layer):
   - GCP region failure detected → Cloud Monitoring alert triggers
   - DR Dialogflow CX agent activated (pre-provisioned, always warm)
   - Cloud Run DR instances auto-scale (min 2 instances always warm)
   - DNS failover for middleware endpoint (if applicable)

3. MANUAL (Full Site DR):
   - Dallas DC complete failure
   - Activate Phoenix Genesys environment
   - Verify Phoenix interconnects are routing to us-central1
   - Update SIP trunk configurations for DR SBC IPs
   - Notify Five9 of SBC endpoint change (if applicable)
   - Estimated full DR activation: 15-30 minutes
```

---


## 14. Latency Analysis

### 14.1 Voice Path Latency Budget (Dallas DC → GCP us-south1)

| # | Segment | Expected Latency | Cumulative | Notes |
|---|---------|-----------------|------------|-------|
| 1 | Dallas DC → Equinix DA7 (AT&T dark fiber) | < 1 ms | 1 ms | ~5-10 km metro fiber |
| 2 | Equinix DA7 → GCP us-south1 (Dedicated Interconnect) | 1-2 ms | 3 ms | Physical cross-connect + GCP edge |
| 3 | GCP edge → GTP endpoint (internal network) | 1-2 ms | 5 ms | Intra-region routing |
| 4 | GTP → Dialogflow CX (STT streaming) | 50-100 ms | 55-105 ms | Speech recognition + NLU processing |
| 5 | Dialogflow CX → TTS synthesis | 20-50 ms | 75-155 ms | Text-to-Speech generation |
| 6 | Return: GTP → Interconnect → SBC | 3-5 ms | 78-160 ms | Network return path |
| | **Total One-Way (Network only, no CCAI)** | **3-5 ms** | | **Excellent** |
| | **Total One-Way (with CCAI processing)** | **~60-80 ms** | | **Within 80ms target** |
| | **Total Round-Trip (network only)** | **6-10 ms** | | **Well within budget** |

### 14.2 Data Path Latency Budget (Genesys ORS → Cloud Run)

| # | Segment | Expected Latency | Notes |
|---|---------|-----------------|-------|
| 1 | ORS → DC network to interconnect router | < 1 ms | LAN segment |
| 2 | Interconnect router → Equinix DA7 (dark fiber) | < 1 ms | Same metro |
| 3 | Equinix DA7 → GCP us-south1 (Dedicated Interconnect) | 1-2 ms | Dedicated link |
| 4 | GCP network → PSC endpoint → Cloud Run | 2-5 ms | VPC connector + cold start (if any) |
| 5 | Cloud Run processing (Firestore query + logic) | 10-30 ms | Application-layer |
| 6 | Return path (same network segments) | 3-5 ms | Network return |
| | **Total Round-Trip** | **~20-45 ms** | **Acceptable for real-time routing** |

### 14.3 DR Path Latency (Phoenix DC → GCP us-central1)

| # | Segment | Expected Latency | Notes |
|---|---------|-----------------|-------|
| 1 | Phoenix DC → Equinix PH1 (AT&T dark fiber) | < 1 ms | Metro fiber |
| 2 | Equinix PH1 → GCP us-central1 (Interconnect) | 15-20 ms | Phoenix to Iowa (~1,500 miles) |
| 3 | GCP internal (us-central1) | 1-2 ms | Intra-region |
| 4 | CCAI processing | 50-100 ms | Same as primary |
| 5 | Return path | 16-22 ms | Reverse network path |
| | **Total One-Way (with CCAI)** | **~85-125 ms** | **Exceeds 80ms target in DR** |

> **DR Latency Advisory:** In a DR scenario using the Phoenix → Iowa path, voice latency will exceed the 80ms target due to the geographic distance. This is an accepted trade-off for DR — the priority is service continuity over optimal latency. End users may perceive slightly increased delay during DR operation.

### 14.4 Cross-Metro Failover Latency (Dallas DC → Phoenix Interconnect → GCP)

| # | Segment | Expected Latency | Notes |
|---|---------|-----------------|-------|
| 1 | Dallas DC → WAN → Phoenix DC | 15-20 ms | AT&T/Verizon WAN backbone |
| 2 | Phoenix DC → Equinix PH1 | < 1 ms | Metro fiber |
| 3 | Equinix PH1 → GCP us-central1 | 15-20 ms | Phoenix to Iowa |
| | **Network path only** | **~30-40 ms** | Increased but functional |
| | **With CCAI processing** | **~100-140 ms** | Above target - DR trade-off |

### 14.5 Latency Monitoring

```yaml
# Cloud Monitoring - Latency SLO
Monitoring Configuration:
  
  Metric 1: Interconnect RTT
    Source: Cloud Router BGP keepalive
    Threshold: Alert if > 5ms (Dallas), > 40ms (Phoenix)
    Window: 5 minutes
    
  Metric 2: Voice Path E2E Latency
    Source: SBC call statistics (SIP OPTIONS ping)
    Threshold: Alert if > 80ms one-way
    Window: 1 minute
    
  Metric 3: Middleware API Latency
    Source: Cloud Run request latency (p99)
    Threshold: Alert if > 100ms (p99)
    Window: 5 minutes
    
  Metric 4: Jitter (RTP)
    Source: SBC RTP statistics
    Threshold: Alert if > 30ms jitter
    Window: 1 minute
    
  Metric 5: Packet Loss
    Source: SBC + Cloud Router
    Threshold: Alert if > 0.1%
    Window: 5 minutes
```

---


## 15. Implementation Checklist

### Phase 1: Pre-Requisites & Procurement (Weeks 1-4)

- [ ] **Carrier Engagement**
  - [ ] Order AT&T dark fiber: Dallas DC → Equinix DA7
  - [ ] Order Verizon dark fiber: Dallas DC → Equinix DA2
  - [ ] Order AT&T dark fiber: Phoenix DC → Equinix PH1
  - [ ] Order Verizon dark fiber: Phoenix DC → DataBank PHX1
  - [ ] Confirm fiber route diversity between carriers
  - [ ] Obtain lead times (typically 45-90 days for dark fiber)

- [ ] **Equinix / DataBank Cross-Connects**
  - [ ] Order cross-connect at Equinix DA7 (single-mode fiber, LC connector)
  - [ ] Order cross-connect at Equinix DA2 (single-mode fiber, LC connector)
  - [ ] Order cross-connect at Equinix PH1 (single-mode fiber, LC connector)
  - [ ] Order cross-connect at DataBank PHX1 (single-mode fiber, LC connector)
  - [ ] Obtain LOA (Letter of Authorization) from GCP for each facility

- [ ] **GCP Project Setup**
  - [ ] Create GCP project for contact center workloads
  - [ ] Enable required APIs: Compute, Dialogflow, Cloud Run, Firestore, Speech, etc.
  - [ ] Configure billing account and budget alerts
  - [ ] Set up organization policies

### Phase 2: GCP Network Infrastructure (Weeks 3-6)

- [ ] **VPC & Subnets**
  - [ ] Create `contact-center-vpc` (custom mode, global routing)
  - [ ] Create all subnets (voice, data, ccai, mgmt) in us-south1 and us-central1
  - [ ] Configure Private Google Access on all subnets
  - [ ] Set up VPC flow logs

- [ ] **Dedicated Interconnect Provisioning**
  - [ ] Provision Dedicated Interconnect: `interconnect-dallas-da7-primary`
  - [ ] Provision Dedicated Interconnect: `interconnect-dallas-da2-secondary`
  - [ ] Provision Dedicated Interconnect: `interconnect-phoenix-ph1-primary`
  - [ ] Provision Dedicated Interconnect: `interconnect-phoenix-phx1-secondary`
  - [ ] Verify physical link status (light levels, link up)

- [ ] **Cloud Routers & VLAN Attachments**
  - [ ] Create Cloud Router: `cloud-router-us-south1`
  - [ ] Create Cloud Router: `cloud-router-us-central1`
  - [ ] Create VLAN attachments (voice-vlan, data-vlan) on each interconnect
  - [ ] Configure BGP sessions (ASN 64512 ↔ 16550)
  - [ ] Enable BFD on all BGP sessions
  - [ ] Verify BGP session establishment

- [ ] **DNS & Private Service Connect**
  - [ ] Configure private DNS zone for googleapis.com
  - [ ] Set up restricted.googleapis.com DNS records
  - [ ] Create PSC endpoints for Cloud Run and Dialogflow
  - [ ] Verify DNS resolution from on-prem (via interconnect)

### Phase 3: Security Configuration (Weeks 5-7)

- [ ] **Firewall Rules**
  - [ ] Implement all ingress/egress firewall rules per Section 11
  - [ ] Verify default-deny is in place
  - [ ] Test connectivity with firewall rules active

- [ ] **VPC Service Controls**
  - [ ] Create access policy and perimeter
  - [ ] Define access levels (on-prem interconnect, service accounts)
  - [ ] Configure ingress/egress policies
  - [ ] Test in dry-run mode before enforcement
  - [ ] Enable enforcement after validation

### Phase 4: Routing & Failover Configuration (Weeks 6-8)

- [ ] **BGP Route Configuration**
  - [ ] Configure on-prem router route advertisements
  - [ ] Set MED values for primary/secondary path selection
  - [ ] Configure local-preference on customer routers
  - [ ] Verify route table on both sides

- [ ] **Failover Testing**
  - [ ] Test single link failure (disable DA7, verify DA2 takes over)
  - [ ] Test carrier failure (simulate AT&T outage)
  - [ ] Test metro failover (Dallas → Phoenix)
  - [ ] Measure BGP convergence time for each scenario
  - [ ] Document actual failover times vs. targets

### Phase 5: Application Layer (Weeks 7-10)

- [ ] **GTP / SIP Trunk Configuration**
  - [ ] Configure Dialogflow CX SIP trunk (telephony.googleapis.com)
  - [ ] Configure Oracle SBC trunk toward GTP
  - [ ] Set codec to G.711u, enable SRTP
  - [ ] Test SIP REGISTER/INVITE/BYE flows
  - [ ] Test media (RTP) path end-to-end

- [ ] **Cloud Run Middleware**
  - [ ] Deploy middleware API to Cloud Run (us-south1)
  - [ ] Deploy DR instance to Cloud Run (us-central1)
  - [ ] Configure VPC connector for private access
  - [ ] Test API calls from Genesys ORS via interconnect

- [ ] **Five9 Integration**
  - [ ] Configure Five9 SIP trunk to Oracle SBC
  - [ ] Whitelist Five9 IPs on SBC
  - [ ] Test Five9 → SBC → GCP flow
  - [ ] Test Five9 → SBC → Genesys flow

### Phase 6: Validation & Go-Live (Weeks 9-12)

- [ ] **Performance Validation**
  - [ ] Measure interconnect latency (target: < 2ms Dallas, < 20ms Phoenix)
  - [ ] Measure voice path latency end-to-end (target: < 80ms)
  - [ ] Run load test: 50 concurrent calls through CCAI path
  - [ ] Verify MOS scores > 4.0 on test calls
  - [ ] Validate middleware API response time (target: < 50ms p95)

- [ ] **Security Validation**
  - [ ] Verify no public IP exposure
  - [ ] Confirm VPC Service Controls block unauthorized access
  - [ ] Test that voice traffic cannot route over public internet
  - [ ] Penetration test on SBC external interface (Five9 facing)

- [ ] **Monitoring & Alerting**
  - [ ] Configure Cloud Monitoring dashboards (latency, throughput, errors)
  - [ ] Set up alerting for interconnect down, high latency, packet loss
  - [ ] Configure SBC monitoring (call quality, SIP errors)
  - [ ] Verify alert routing to operations team

- [ ] **Go-Live**
  - [ ] Conduct go/no-go review with all stakeholders
  - [ ] Migrate pilot call flow (small % of traffic)
  - [ ] Monitor for 48 hours
  - [ ] Full traffic cutover
  - [ ] Post-go-live review (1 week)

---


## 16. Cost Estimate (Monthly)

### 16.1 GCP Dedicated Interconnect Costs

| Item | Quantity | Unit Cost | Monthly Cost | Notes |
|------|----------|-----------|--------------|-------|
| Dedicated Interconnect Port (10 Gbps) | 4 | $1,700/month | **$6,800** | DA7, DA2, PH1, PHX1 |
| VLAN Attachment (Dedicated) | 8 | $75/month | **$600** | 2 per interconnect (voice + data) |
| Cloud Router | 2 | Included | **$0** | No additional charge |
| Interconnect Egress (us-south1) | ~100 GB | $0.02/GB | **$2** | Voice + data return traffic |
| Interconnect Egress (us-central1) | ~50 GB | $0.02/GB | **$1** | DR traffic (minimal in normal ops) |
| **Subtotal - Interconnect** | | | **$7,403** | |

### 16.2 Colocation / Cross-Connect Costs

| Item | Quantity | Unit Cost | Monthly Cost | Notes |
|------|----------|-----------|--------------|-------|
| Equinix DA7 - Cross-connect (fiber) | 1 | $300/month | **$300** | Single-mode, LC |
| Equinix DA2 - Cross-connect (fiber) | 1 | $300/month | **$300** | Single-mode, LC |
| Equinix PH1 - Cross-connect (fiber) | 1 | $350/month | **$350** | Single-mode, LC |
| DataBank PHX1 - Cross-connect (fiber) | 1 | $400/month | **$400** | Single-mode, LC |
| **Subtotal - Cross-Connects** | | | **$1,350** | |

### 16.3 Carrier Dark Fiber (AT&T / Verizon)

| Item | Quantity | Unit Cost | Monthly Cost | Notes |
|------|----------|-----------|--------------|-------|
| AT&T Dark Fiber - Dallas DC → Equinix DA7 | 1 pair | ~$500/month | **$500** | Varies by distance |
| Verizon Dark Fiber - Dallas DC → Equinix DA2 | 1 pair | ~$600/month | **$600** | Varies by distance |
| AT&T Dark Fiber - Phoenix DC → Equinix PH1 | 1 pair | ~$500/month | **$500** | Varies by distance |
| Verizon Dark Fiber - Phoenix DC → DataBank PHX1 | 1 pair | ~$600/month | **$600** | Varies by distance |
| **Subtotal - Dark Fiber** | | | **$2,200** | Estimate; requires carrier quotes |

### 16.4 GCP Compute & Services (Interconnect-Adjacent)

| Item | Quantity | Unit Cost | Monthly Cost | Notes |
|------|----------|-----------|--------------|-------|
| Cloud Run (Middleware) - us-south1 | 2 min instances | ~$50/month | **$50** | Always-warm instances |
| Cloud Run (DR) - us-central1 | 2 min instances | ~$50/month | **$50** | DR warm standby |
| Dialogflow CX (usage-based) | 10,000 sessions/day | ~$0.007/session | **$2,100** | Voice interactions |
| Cloud Speech-to-Text | ~10,000 min/day | ~$0.006/15 sec | **$2,400** | Streaming STT |
| Private Service Connect | 2 endpoints | Included | **$0** | No additional charge |
| VPC Flow Logs | ~50 GB/month | $0.50/GB | **$25** | Voice + data subnets |
| **Subtotal - GCP Services** | | | **$4,625** | Usage-dependent |

### 16.5 Total Monthly Cost Summary

```
┌─────────────────────────────────────────────────────────────────┐
│              MONTHLY COST ESTIMATE - SUMMARY                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  GCP Dedicated Interconnect (ports + VLANs + egress):  $ 7,403  │
│  Cross-Connect Fees (4 facilities):                    $ 1,350  │
│  Carrier Dark Fiber (AT&T + Verizon):                  $ 2,200  │
│  ───────────────────────────────────────────────────────────────  │
│  TOTAL INTERCONNECT INFRASTRUCTURE:                    $ 10,953  │
│                                                                   │
│  GCP Services (Cloud Run, CCAI, STT):                  $ 4,625  │
│  ───────────────────────────────────────────────────────────────  │
│  GRAND TOTAL (Infrastructure + Services):              $ 15,578  │
│                                                                   │
│  * Interconnect-only cost: ~$9,000-11,000/month                  │
│  * Carrier dark fiber costs are estimates pending quotes          │
│  * CCAI/STT costs are usage-dependent and may vary               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 16.6 One-Time Costs

| Item | Cost | Notes |
|------|------|-------|
| GCP Interconnect Setup Fee | $0 | No setup fee for Dedicated Interconnect |
| Equinix Cross-Connect NRC (×4) | ~$1,000-2,000 | One-time installation per connection |
| Carrier Dark Fiber Installation (×4) | ~$5,000-15,000 | Varies significantly by distance and carrier |
| Oracle SBC Configuration (labor) | Internal | Customer engineering team |
| GCP Network Engineering (labor) | ~$25,000-50,000 | Professional services or internal |
| **Total One-Time** | **~$31,000-67,000** | Range depending on carrier quotes |

---

## Appendix A: Key Contacts and Escalation

| Role | Responsibility | Escalation Path |
|------|---------------|-----------------|
| GCP TAM | Interconnect provisioning, GCP service issues | Google Cloud Support (P1) |
| AT&T Account Team | Dark fiber delivery, circuit issues | AT&T Enterprise NOC |
| Verizon Account Team | Dark fiber delivery, circuit issues | Verizon Enterprise NOC |
| Equinix Smart Hands | Cross-connect installation, physical layer | Equinix IBX Support |
| DataBank Support | Cross-connect installation (PHX1) | DataBank NOC |
| Customer Network Eng. | On-prem router, SBC, BGP configuration | Internal escalation |

---

## Appendix B: Acronyms

| Acronym | Definition |
|---------|-----------|
| BFD | Bidirectional Forwarding Detection |
| BGP | Border Gateway Protocol |
| CCAI | Contact Center AI (Google) |
| CX | Customer Experience (Dialogflow CX) |
| DC | Data Center |
| DR | Disaster Recovery |
| GTP | Google Telephony Platform |
| HA | High Availability |
| IAP | Identity-Aware Proxy |
| LOA | Letter of Authorization |
| MED | Multi-Exit Discriminator (BGP) |
| MOS | Mean Opinion Score |
| NLU | Natural Language Understanding |
| NRC | Non-Recurring Charge |
| ORS | Orchestration Server (Genesys) |
| PSC | Private Service Connect |
| RTO | Recovery Time Objective |
| RTP | Real-time Transport Protocol |
| SBC | Session Border Controller |
| SIP | Session Initiation Protocol |
| SLA | Service Level Agreement |
| SRTP | Secure Real-time Transport Protocol |
| STT | Speech-to-Text |
| TLS | Transport Layer Security |
| TTS | Text-to-Speech |
| VIP | Virtual IP Address |
| VLAN | Virtual Local Area Network |
| VPC | Virtual Private Cloud |
| VRRP | Virtual Router Redundancy Protocol |

---

*Document End — Last Updated: 2024-01-15*
