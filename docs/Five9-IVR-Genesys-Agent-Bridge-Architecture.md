# Five9 IVR Front-End + Genesys Agent Back-End: Voice & Data Bridge Architecture

## Executive Summary

This document describes the complete architecture and configuration for a **hybrid voice bridge** where:
- **Five9** serves as the **IVR front-end** (menu routing, data collection)
- **Genesys Engage (on-prem)** provides the **agent back-end** (all agents remain on Genesys)
- **Oracle/Acme Packet SBC** (dual) provides SIP interconnection and media bridging
- **GCP Cloud Run middleware** provides the data bridge and correlation layer
- **Call data is conserved** across both platforms with a unified correlation ID

This is a **temporary migration architecture** supporting the transition from on-prem Genesys to Five9 CCaaS.

---

## Design Parameters

| Parameter | Value |
|---|---|
| Volume | ~10,000 calls/day (~420 calls/hour peak, ~7 concurrent transfers/min) |
| Five9 Role | IVR only (menu routing) + some self-service termination |
| Genesys Role | All agent interactions (Skills, Queues, Agent Groups) |
| Transfer Direction | Primarily Five9 → Genesys; occasionally Genesys → Five9 |
| Media Path | Five9 stays in path (for recording/post-call survey) |
| ANI | Original caller ANI preserved end-to-end |
| Context | Full bidirectional data conservation |
| Correlation | Unified call UUID across both platforms |
| SBC | Oracle/Acme Packet (Dual HA) |
| Genesys Topology | SIP Server HA Pair |
| Failover | If Genesys down → keep in Five9 queue / offer callback |
| Duration | Temporary (migration period) |

---

## 1. End-to-End Call Flow

### 1.1 High-Level Flow Diagram

```
                          ┌─────────────────────────────────────────┐
                          │            FIVE9 CLOUD                   │
                          │                                         │
  Caller ──→ PSTN ──→ SBC-A ──→ Five9 IVR (Menu Routing)          │
                          │         │                               │
                          │    [Collects: Language, Intent,          │
                          │     Menu Choice, CustomerID]             │
                          │         │                               │
                          │    ┌────┴────────────────┐              │
                          │    │                     │              │
                          │  Self-Service         Transfer          │
                          │  (terminate on Five9)  to Agent         │
                          │                          │              │
                          └──────────────────────────┼──────────────┘
                                                     │
                              SIP INVITE + X-Headers  │  (via SBC)
                              (carries all IVR data)  │
                                                     ▼
                          ┌─────────────────────────────────────────┐
                          │        ORACLE SBC (Dual HA)             │
                          │                                         │
                          │  • Header Manipulation (HMR)            │
                          │  • ANI preservation (P-Asserted-Id)     │
                          │  • Media anchoring (stays in path)      │
                          │  • Failover routing                     │
                          │  • TLS termination                      │
                          │                                         │
                          └────────────────────┬────────────────────┘
                                               │
                              SIP INVITE + X-Headers (normalized)
                              P-Asserted-Identity: original ANI
                                               │
                                               ▼
                          ┌─────────────────────────────────────────┐
                          │     GCP CLOUD RUN MIDDLEWARE             │
                          │     (Data Bridge - HTTP webhook)         │
                          │                                         │
                          │  • Receives webhook from Five9 pre-     │
                          │    transfer with full call context       │
                          │  • Generates correlation UUID           │
                          │  • Stores context in Firestore/Redis    │
                          │  • Provides API for Genesys to fetch    │
                          │    full context on call arrival          │
                          │                                         │
                          └─────────────────────────────────────────┘
                                               │
                                               ▼
                          ┌─────────────────────────────────────────┐
                          │     GENESYS ENGAGE (ON-PREM)            │
                          │                                         │
                          │  SIP Server (HA Pair)                   │
                          │       │                                 │
                          │  Routing Point (reads X-headers)        │
                          │       │                                 │
                          │  ORS/URS Strategy                       │
                          │  (parses intent → selects queue)        │
                          │       │                                 │
                          │  Agent Desktop (screen pop with         │
                          │  full Five9 IVR context)                │
                          │                                         │
                          └─────────────────────────────────────────┘
```

### 1.2 SIP Ladder Diagram (Transfer Flow)

```
  Caller          Five9 IVR       Oracle SBC-A      GCP Middleware     Genesys SIP Svr    ORS        Agent
    │                │                │                  │                  │              │            │
    │── INVITE ─────►│                │                  │                  │              │            │
    │◄── 200 OK ─────│                │                  │                  │              │            │
    │◄═══ RTP ══════►│                │                  │                  │              │            │
    │                │                │                  │                  │              │            │
    │   [IVR Menu plays, caller selects option]          │                  │              │            │
    │                │                │                  │                  │              │            │
    │                │──── HTTP POST (pre-transfer) ────►│                  │              │            │
    │                │    {ANI, DNIS, intent, CAVs,      │                  │              │            │
    │                │     callUUID, timestamp}          │                  │              │            │
    │                │◄─── 200 {correlationId} ──────────│                  │              │            │
    │                │                │                  │                  │              │            │
    │                │── INVITE ─────►│                  │                  │              │            │
    │                │  To: genesys-rp@sbc              │                  │              │            │
    │                │  X-Five9-CallUUID: abc123         │                  │              │            │
    │                │  X-Five9-Intent: billing          │                  │              │            │
    │                │  X-Five9-CustID: C99001           │                  │              │            │
    │                │  X-Five9-Language: en             │                  │              │            │
    │                │  X-Five9-CorrelationId: uuid-xxx  │                  │              │            │
    │                │  P-Asserted-Id: <original ANI>    │                  │              │            │
    │                │                │                  │                  │              │            │
    │                │                │── INVITE ───────────────────────────►│              │            │
    │                │                │  (HMR: normalize headers)           │              │            │
    │                │                │  X-Bridge-CorrelationId: uuid-xxx   │              │            │
    │                │                │  X-Bridge-Intent: billing           │              │            │
    │                │                │  X-Bridge-CustID: C99001            │              │            │
    │                │                │  X-Bridge-Language: en              │              │            │
    │                │                │  X-Bridge-CallUUID: abc123          │              │            │
    │                │                │  P-Asserted-Identity: +15551234567  │              │            │
    │                │                │                  │                  │              │            │
    │                │                │                  │                  │── RouteReq ──►│            │
    │                │                │                  │                  │              │            │
    │                │                │                  │                  │   [ORS reads X-headers,   │
    │                │                │                  │                  │    calls middleware API,   │
    │                │                │                  │                  │    gets full context]      │
    │                │                │                  │                  │              │            │
    │                │                │                  │◄── GET /context/{uuid-xxx} ────│            │
    │                │                │                  │──── {full context JSON} ──────►│            │
    │                │                │                  │                  │              │            │
    │                │                │                  │                  │◄─ RouteCall ─│            │
    │                │                │                  │                  │  (target: AG_Billing)     │
    │                │                │                  │                  │              │            │
    │                │                │                  │                  │── INVITE ────────────────►│
    │                │                │                  │                  │  + UserData attached      │
    │                │                │◄── 200 OK ──────────────────────────│              │            │
    │                │◄── 200 OK ─────│                  │                  │              │            │
    │                │                │                  │                  │              │            │
    │◄═══════════ RTP (media bridged through SBC, Five9 stays in path) ════════════════════════════════►│
    │                │                │                  │                  │              │            │
    │   [Agent handles call with full context screen pop]│                  │              │            │
    │                │                │                  │                  │              │            │
    │◄── BYE ────────────────────────────────────────────────────────────────────────────────────────────│
    │                │                │                  │                  │              │            │
    │   [Five9 captures post-call metrics, recording segment]              │              │            │
    │                │                │                  │                  │              │            │
```

### 1.3 Call States Summary

| Step | Platform | Action | Data |
|---|---|---|---|
| 1 | PSTN → SBC → Five9 | Caller dials, SBC routes to Five9 | ANI, DNIS |
| 2 | Five9 IVR | Menu plays, caller selects option | Language, Intent, Menu choice |
| 3 | Five9 IVR | Optional: authentication, account lookup | CustomerID, Account Balance |
| 4 | Five9 | Pre-transfer webhook to GCP middleware | All collected data + Five9 UUID |
| 5 | GCP Middleware | Stores context, generates correlation ID | Returns correlationId |
| 6 | Five9 → SBC | SIP INVITE with X-headers + correlation ID | Full context in SIP headers |
| 7 | SBC | HMR normalizes headers, preserves ANI | Translates header format |
| 8 | SBC → Genesys | Forwards INVITE to Genesys Routing Point | Normalized headers |
| 9 | Genesys ORS | Reads headers, calls middleware for full context | Routing decision |
| 10 | Genesys ORS | Routes to appropriate Agent Group/Queue | UserData attached |
| 11 | Genesys Agent | Receives call + screen pop with IVR context | Full Five9 data visible |
| 12 | Post-call | Both platforms log with shared correlation ID | Unified reporting |



---

## 2. Five9 IVR Script Configuration

### 2.1 Five9 VCC SIP Trunk Setup

```
Five9 VCC Administrator > VCC Configuration > SIP Trunks

┌─────────────────────────────────────────────────────────────────┐
│ Trunk Name:         Genesys_Bridge_Trunk                        │
│ Direction:          Outbound (Five9 → SBC → Genesys)            │
│ Protocol:           SIP over TLS                                │
│ Transport:          TLS (port 5061)                             │
│                                                                 │
│ Outbound Proxy:                                                 │
│   Primary:          sbc-a.company.com:5061                      │
│   Secondary:        sbc-b.company.com:5061                      │
│                                                                 │
│ Authentication:     IP-Based + Digest                           │
│   Username:         five9_bridge                                │
│   Password:         <secure_password>                           │
│                                                                 │
│ Codec Preferences:                                              │
│   1. G.711u (PCMU/8000)                                        │
│   2. G.711a (PCMA/8000)                                        │
│   3. G.729                                                      │
│                                                                 │
│ DTMF Method:        RFC 2833                                    │
│ Max Concurrent:     200                                         │
│                                                                 │
│ ANI Handling:       Pass Original Caller ANI                    │
│ P-Asserted-Id:      Include original caller number              │
│                                                                 │
│ Custom Headers:     Enabled (allow X-Five9-* headers outbound)  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Five9 Inbound Campaign (Receiving Calls from SBC)

```
Five9 VCC Administrator > Campaigns > Inbound

Campaign Name:        Bridge_IVR_Front
Campaign Type:        Inbound
DNIS Assignments:
  - 18005551234      (Main Support)
  - 18005551235      (Sales)
  - 18005551236      (Billing)
  - 18005551237      (Technical)

IVR Script:           Bridge_Menu_Router (see below)
Max Queue Wait:       N/A (IVR only, no agent queue on Five9)
Skill Group:          IVR_Only_Skill (placeholder, no agents assigned)
```

### 2.3 Five9 Call Variables (CAV) Definition

```
Five9 VCC Administrator > Call Variables

CAV Group: Bridge_Context
┌─────────────────────┬──────────┬─────────────────────────────────────┐
│ Variable Name       │ Type     │ Description                         │
├─────────────────────┼──────────┼─────────────────────────────────────┤
│ CorrelationId       │ String   │ Unique UUID for cross-platform ID   │
│ CallerANI           │ String   │ Original caller phone number        │
│ CalledDNIS          │ String   │ Original DNIS dialed                │
│ Language            │ String   │ Language selected (en/es/fr)         │
│ MenuChoice          │ String   │ IVR menu option selected            │
│ Intent              │ String   │ Derived intent/reason code          │
│ CustomerID          │ String   │ Authenticated customer ID           │
│ AccountBalance      │ String   │ Account balance (if looked up)      │
│ IVRTimestamp        │ String   │ ISO 8601 timestamp of IVR entry     │
│ TransferTarget      │ String   │ Genesys queue/skill target          │
│ Five9CallUUID       │ String   │ Five9 internal call session ID      │
│ Priority            │ String   │ Call priority (high/normal/low)     │
└─────────────────────┴──────────┴─────────────────────────────────────┘
```

### 2.4 Five9 IVR Script: Bridge_Menu_Router

This is the core Five9 Visual IVR / Studio script:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FIVE9 IVR SCRIPT: Bridge_Menu_Router                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐                                                        │
│  │   START     │                                                        │
│  │  (Inbound)  │                                                        │
│  └──────┬──────┘                                                        │
│         │                                                                │
│  ┌──────▼──────────────────────────────────┐                            │
│  │  SET VARIABLES                          │                            │
│  │  • CallerANI = {system.ani}             │                            │
│  │  • CalledDNIS = {system.dnis}           │                            │
│  │  • Five9CallUUID = {system.callId}      │                            │
│  │  • IVRTimestamp = {system.timestamp}    │                            │
│  │  • CorrelationId = UUID()               │  ← Generate unique ID     │
│  └──────┬──────────────────────────────────┘                            │
│         │                                                                │
│  ┌──────▼──────────────────────────────────┐                            │
│  │  PLAY GREETING                          │                            │
│  │  "Welcome to Company X..."              │                            │
│  │  "Para español, oprima 2"               │                            │
│  └──────┬──────────────────────────────────┘                            │
│         │                                                                │
│  ┌──────▼──────────────────────────────────┐                            │
│  │  LANGUAGE SELECTION (DTMF)              │                            │
│  │  1 = English                            │                            │
│  │  2 = Spanish                            │                            │
│  │  → Set Language = "en" / "es"           │                            │
│  └──────┬──────────────────────────────────┘                            │
│         │                                                                │
│  ┌──────▼──────────────────────────────────┐                            │
│  │  MAIN MENU (DTMF)                       │                            │
│  │  "Press 1 for Billing"                  │                            │
│  │  "Press 2 for Technical Support"        │                            │
│  │  "Press 3 for Sales"                    │                            │
│  │  "Press 4 for Account Balance"          │                            │
│  │  "Press 0 for Operator"                 │                            │
│  └──────┬──────────────────────────────────┘                            │
│         │                                                                │
│  ┌──────▼──────────────────────────────────────────────────────────┐    │
│  │  CASE / BRANCHING                                                │    │
│  │                                                                  │    │
│  │  OPTION 1 (Billing):                                            │    │
│  │    → Intent = "billing"                                          │    │
│  │    → MenuChoice = "1"                                           │    │
│  │    → TransferTarget = "RP_Billing"                              │    │
│  │    → Priority = "normal"                                        │    │
│  │    → GOTO: PRE_TRANSFER_WEBHOOK                                 │    │
│  │                                                                  │    │
│  │  OPTION 2 (Technical):                                          │    │
│  │    → Intent = "technical_support"                                │    │
│  │    → MenuChoice = "2"                                           │    │
│  │    → TransferTarget = "RP_TechSupport"                          │    │
│  │    → Priority = "normal"                                        │    │
│  │    → GOTO: PRE_TRANSFER_WEBHOOK                                 │    │
│  │                                                                  │    │
│  │  OPTION 3 (Sales):                                              │    │
│  │    → Intent = "sales"                                            │    │
│  │    → MenuChoice = "3"                                           │    │
│  │    → TransferTarget = "RP_Sales"                                │    │
│  │    → Priority = "high"                                          │    │
│  │    → GOTO: PRE_TRANSFER_WEBHOOK                                 │    │
│  │                                                                  │    │
│  │  OPTION 4 (Account Balance - SELF SERVICE):                     │    │
│  │    → Intent = "self_service_balance"                             │    │
│  │    → MenuChoice = "4"                                           │    │
│  │    → GOTO: SELF_SERVICE_MODULE                                  │    │
│  │                                                                  │    │
│  │  OPTION 0 (Operator):                                           │    │
│  │    → Intent = "operator"                                         │    │
│  │    → MenuChoice = "0"                                           │    │
│  │    → TransferTarget = "RP_General"                              │    │
│  │    → Priority = "high"                                          │    │
│  │    → GOTO: PRE_TRANSFER_WEBHOOK                                 │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  SELF_SERVICE_MODULE (Option 4 only)                            │    │
│  │  • Authenticate customer (PIN/last 4 SSN)                       │    │
│  │  • Lookup account balance via HTTP connector                    │    │
│  │  • Play balance to caller                                       │    │
│  │  • "Press 1 to speak with an agent, Press 2 to end call"       │    │
│  │                                                                  │    │
│  │  IF press 1:                                                    │    │
│  │    → Intent = "balance_then_agent"                              │    │
│  │    → TransferTarget = "RP_Billing"                              │    │
│  │    → GOTO: PRE_TRANSFER_WEBHOOK                                 │    │
│  │  IF press 2:                                                    │    │
│  │    → GOTO: END_CALL (self-service complete)                     │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  PRE_TRANSFER_WEBHOOK (HTTP Module)                             │    │
│  │                                                                  │    │
│  │  Method: POST                                                   │    │
│  │  URL: https://bridge-api-xxxxx.run.app/api/v1/pre-transfer      │    │
│  │                                                                  │    │
│  │  Body (JSON):                                                    │    │
│  │  {                                                               │    │
│  │    "correlationId": "{CorrelationId}",                          │    │
│  │    "five9CallUUID": "{Five9CallUUID}",                          │    │
│  │    "callerANI": "{CallerANI}",                                  │    │
│  │    "calledDNIS": "{CalledDNIS}",                                │    │
│  │    "language": "{Language}",                                     │    │
│  │    "menuChoice": "{MenuChoice}",                                │    │
│  │    "intent": "{Intent}",                                        │    │
│  │    "customerID": "{CustomerID}",                                │    │
│  │    "accountBalance": "{AccountBalance}",                        │    │
│  │    "transferTarget": "{TransferTarget}",                        │    │
│  │    "priority": "{Priority}",                                    │    │
│  │    "ivrTimestamp": "{IVRTimestamp}",                             │    │
│  │    "ivrDuration": "{system.callDuration}"                       │    │
│  │  }                                                               │    │
│  │                                                                  │    │
│  │  Response: Store middleware response (confirmation)              │    │
│  └──────┬───────────────────────────────────────────────────────────┘    │
│         │                                                                │
│  ┌──────▼──────────────────────────────────────────────────────────┐    │
│  │  SIP HEADER MODULE (Set outbound X-headers for transfer)        │    │
│  │                                                                  │    │
│  │  Set the following XSIP headers:                                │    │
│  │    X-Five9-CorrelationId  = {CorrelationId}                     │    │
│  │    X-Five9-Intent         = {Intent}                            │    │
│  │    X-Five9-CustID         = {CustomerID}                        │    │
│  │    X-Five9-Language       = {Language}                          │    │
│  │    X-Five9-MenuChoice     = {MenuChoice}                        │    │
│  │    X-Five9-Priority       = {Priority}                          │    │
│  │    X-Five9-TransferTarget = {TransferTarget}                    │    │
│  │    X-Five9-CallUUID       = {Five9CallUUID}                     │    │
│  │    X-Five9-ANI            = {CallerANI}                         │    │
│  │    X-Five9-DNIS           = {CalledDNIS}                        │    │
│  │    X-Five9-Timestamp      = {IVRTimestamp}                      │    │
│  │    X-Five9-Balance        = {AccountBalance}                    │    │
│  └──────┬───────────────────────────────────────────────────────────┘    │
│         │                                                                │
│  ┌──────▼──────────────────────────────────────────────────────────┐    │
│  │  THIRD-PARTY TRANSFER MODULE                                    │    │
│  │                                                                  │    │
│  │  Transfer Type:    Third Party Transfer (bridge/consultative)   │    │
│  │  Destination:      sip:{TransferTarget}@sbc-a.company.com      │    │
│  │  Trunk:            Genesys_Bridge_Trunk                         │    │
│  │  Keep Five9 in path: YES (for recording + post-call)           │    │
│  │  ANI Override:      {CallerANI} (preserve original)            │    │
│  │  Timeout:           30 seconds                                  │    │
│  │                                                                  │    │
│  │  On Success: → GOTO: MONITOR_CALL                              │    │
│  │  On Failure: → GOTO: TRANSFER_FAILED                           │    │
│  └──────┬───────────────────────────────────────────────────────────┘    │
│         │                                                                │
│  ┌──────▼──────────────────────────────────────────────────────────┐    │
│  │  MONITOR_CALL                                                   │    │
│  │  • Five9 remains in media path (recording active)              │    │
│  │  • On BYE from Genesys agent: → GOTO POST_CALL_SURVEY          │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  TRANSFER_FAILED (Failover)                                     │    │
│  │  • "We're experiencing high volume..."                          │    │
│  │  • "Press 1 for callback, Press 2 to wait"                     │    │
│  │  • IF callback: collect callback number, schedule via API       │    │
│  │  • IF wait: queue on Five9 with MOH (hold until Genesys up)    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  END_CALL (Self-service completion)                             │    │
│  │  • "Thank you, goodbye"                                         │    │
│  │  • Disconnect                                                   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.5 Five9 Studio Script (XSIP Header Configuration)

In Five9 Studio, the SIP Header node configuration:

```
Node: SIP Header (pre-transfer)
Type: REFER headers (sent with blind transfer) OR INVITE headers (third-party)

Headers to set on outbound INVITE:
┌────────────────────────────────────────────────────────────────────┐
│ Header Name              │ Value                │ Direction        │
├──────────────────────────┼──────────────────────┼──────────────────┤
│ X-Five9-CorrelationId    │ %CorrelationId%      │ Outbound INVITE  │
│ X-Five9-Intent           │ %Intent%             │ Outbound INVITE  │
│ X-Five9-CustID           │ %CustomerID%         │ Outbound INVITE  │
│ X-Five9-Language         │ %Language%           │ Outbound INVITE  │
│ X-Five9-MenuChoice       │ %MenuChoice%         │ Outbound INVITE  │
│ X-Five9-Priority         │ %Priority%           │ Outbound INVITE  │
│ X-Five9-TransferTarget   │ %TransferTarget%     │ Outbound INVITE  │
│ X-Five9-CallUUID         │ %Five9CallUUID%      │ Outbound INVITE  │
│ X-Five9-ANI              │ %CallerANI%          │ Outbound INVITE  │
│ X-Five9-DNIS             │ %CalledDNIS%         │ Outbound INVITE  │
│ X-Five9-Timestamp        │ %IVRTimestamp%       │ Outbound INVITE  │
│ X-Five9-Balance          │ %AccountBalance%     │ Outbound INVITE  │
└────────────────────────────────────────────────────────────────────┘

Note: Five9 Studio converts header names to lowercase and replaces 
dashes with underscores internally. The SBC HMR must account for this.
Actual outbound header may appear as: x-five9-correlationid
```



---

## 3. Oracle/Acme Packet SBC Configuration

### 3.1 Architecture Overview

```
                    ┌────────────────────────────────────────────────┐
                    │         ORACLE SBC (Dual HA)                    │
                    │                                                │
  Five9 Cloud ─────►│  SIP Interface: external-five9 (realm: five9) │
  (TLS 5061)       │         │                                      │
                    │         ▼                                      │
                    │  [Classification] → [Local Policy] → [Routing]│
                    │         │                                      │
                    │         ▼                                      │
  Genesys SIP ◄────│  SIP Interface: internal-genesys (realm: gns) │
  (TCP 5060)       │                                                │
                    │                                                │
  PSTN Carrier ───►│  SIP Interface: external-pstn (realm: pstn)   │
  (TCP 5060)       │                                                │
                    └────────────────────────────────────────────────┘
```

### 3.2 Physical/Network Interfaces

```
ORACLE-SBC# configure terminal
ORACLE-SBC(configure)# system
ORACLE-SBC(system)# phy-interface
ORACLE-SBC(phy-interface)#

; Interface facing Five9 (external/WAN)
phy-interface
    name                     M00
    operation-type           Media
    port                     0
    slot                     0

; Interface facing Genesys (internal/LAN)  
phy-interface
    name                     M10
    operation-type           Media
    port                     1
    slot                     0
```

### 3.3 Network Interfaces

```
ORACLE-SBC(configure)# system
ORACLE-SBC(system)# network-interface

; External network (Five9 + PSTN facing)
network-interface
    name                     external-net
    sub-port-id              0
    ip-address               203.0.113.10        ; Public IP facing Five9
    netmask                  255.255.255.0
    gateway                  203.0.113.1
    sec-gateway              0.0.0.0
    phy-interface            M00
    dns-ip-primary           8.8.8.8
    dns-ip-backup1           8.8.4.4
    hip-ip-list              203.0.113.10, 203.0.113.11

; Internal network (Genesys facing)
network-interface
    name                     internal-net
    sub-port-id              0
    ip-address               10.1.0.50           ; Internal IP facing Genesys
    netmask                  255.255.255.0
    gateway                  10.1.0.1
    phy-interface            M10
    hip-ip-list              10.1.0.50, 10.1.0.51
```

### 3.4 Realms

```
ORACLE-SBC(configure)# media-manager
ORACLE-SBC(media-manager)# realm-config

; Five9 realm (external)
realm-config
    identifier               five9
    description              "Five9 Cloud CCaaS"
    network-interfaces       external-net:0
    media-policy             media-policy-five9
    mm-in-realm              enabled
    mm-in-network            enabled
    out-translationid        0
    in-translationid         0
    symmetrical-latching     enabled
    parent-realm             ""
    dns-realm                enabled

; PSTN realm (external)
realm-config
    identifier               pstn
    description              "PSTN Carrier Trunks"
    network-interfaces       external-net:0
    media-policy             media-policy-pstn
    mm-in-realm              enabled
    symmetrical-latching     enabled
    parent-realm             ""

; Genesys realm (internal)
realm-config
    identifier               genesys
    description              "Genesys Engage On-Prem"
    network-interfaces       internal-net:0
    media-policy             media-policy-genesys
    mm-in-realm              enabled
    symmetrical-latching     enabled
    parent-realm             ""
```

### 3.5 SIP Interfaces

```
ORACLE-SBC(configure)# session-router
ORACLE-SBC(session-router)# sip-interface

; SIP Interface: Five9 (external, TLS)
sip-interface
    state                    enabled
    realm-id                 five9
    description              "Five9 Cloud SIP Interface"
    sip-port
        address              203.0.113.10
        port                 5061
        transport-protocol   tls
        tls-profile          five9-tls-profile
    allow-anonymous          agents-only
    registration-caching     enabled
    options-ping-interval    60

; SIP Interface: PSTN Carrier (external, TCP)
sip-interface
    state                    enabled
    realm-id                 pstn
    description              "PSTN Carrier SIP Interface"
    sip-port
        address              203.0.113.10
        port                 5060
        transport-protocol   tcp
    allow-anonymous          agents-only

; SIP Interface: Genesys (internal, TCP)
sip-interface
    state                    enabled
    realm-id                 genesys
    description              "Genesys SIP Server Interface"
    sip-port
        address              10.1.0.50
        port                 5060
        transport-protocol   tcp
    allow-anonymous          agents-only
    options-ping-interval    30
```

### 3.6 TLS Profile (for Five9 connectivity)

```
ORACLE-SBC(configure)# security
ORACLE-SBC(security)# tls-profile

tls-profile
    name                     five9-tls-profile
    end-entity-certificate   sbc-server-cert
    trusted-ca-certificates  five9-ca-bundle
    cipher-list              RSA_WITH_AES_256_CBC_SHA,RSA_WITH_AES_128_CBC_SHA
    verify-depth             3
    mutual-authentication    disabled
    tls-version              tlsv12
    cert-status-check        enabled
```

### 3.7 Session Agents

```
ORACLE-SBC(configure)# session-router
ORACLE-SBC(session-router)# session-agent

; Session Agent: Five9 Primary Gateway
session-agent
    hostname                 five9-primary
    ip-address               <five9-dc1-ip>      ; Five9 data center 1
    port                     5061
    state                    enabled
    app-protocol             SIP
    transport-method         TLS
    realm-id                 five9
    description              "Five9 Primary SBC Gateway"
    max-sessions             200
    max-inbound-sessions     100
    max-outbound-sessions    200
    ping-method              OPTIONS
    ping-interval            60
    ping-send-mode           keep-alive
    out-service-503          enabled
    options-ping-interval    30
    tls-profile              five9-tls-profile

; Session Agent: Five9 Secondary Gateway  
session-agent
    hostname                 five9-secondary
    ip-address               <five9-dc2-ip>      ; Five9 data center 2
    port                     5061
    state                    enabled
    app-protocol             SIP
    transport-method         TLS
    realm-id                 five9
    description              "Five9 Secondary SBC Gateway"
    max-sessions             200
    ping-method              OPTIONS
    ping-interval            60
    out-service-503          enabled
    tls-profile              five9-tls-profile

; Session Agent: Genesys SIP Server Primary
session-agent
    hostname                 genesys-sip-primary
    ip-address               10.1.0.10
    port                     5060
    state                    enabled
    app-protocol             SIP
    transport-method         TCP
    realm-id                 genesys
    description              "Genesys SIP Server Primary (HA)"
    max-sessions             500
    max-inbound-sessions     500
    max-outbound-sessions    500
    ping-method              OPTIONS
    ping-interval            30
    ping-send-mode           keep-alive
    out-service-503          enabled
    reuse-connections        TCP

; Session Agent: Genesys SIP Server Backup
session-agent
    hostname                 genesys-sip-backup
    ip-address               10.1.0.11
    port                     5060
    state                    enabled
    app-protocol             SIP
    transport-method         TCP
    realm-id                 genesys
    description              "Genesys SIP Server Backup (HA)"
    max-sessions             500
    ping-method              OPTIONS
    ping-interval            30
    out-service-503          enabled
    reuse-connections        TCP

; Session Agent: PSTN Carrier
session-agent
    hostname                 pstn-carrier
    ip-address               198.51.100.20
    port                     5060
    state                    enabled
    app-protocol             SIP
    transport-method         TCP
    realm-id                 pstn
    description              "PSTN SIP Carrier"
    max-sessions             1000
    ping-method              OPTIONS
    ping-interval            60
```

### 3.8 Session Agent Groups (for HA failover)

```
ORACLE-SBC(session-router)# session-agent-group

; Five9 HA Group
session-agent-group
    group-name               SAG-Five9
    description              "Five9 Gateway HA Group"
    strategy                 LeastBusy
    dest
        hostname             five9-primary
        priority             1
    dest
        hostname             five9-secondary
        priority             2

; Genesys HA Group
session-agent-group
    group-name               SAG-Genesys
    description              "Genesys SIP Server HA Group"
    strategy                 RoundRobin
    dest
        hostname             genesys-sip-primary
        priority             1
    dest
        hostname             genesys-sip-backup
        priority             2
```

### 3.9 Local Policies (Routing Logic)

```
ORACLE-SBC(session-router)# local-policy

; ========================================================
; POLICY 1: PSTN Carrier → Five9 (Inbound calls to IVR)
; All inbound PSTN calls go to Five9 IVR first
; ========================================================
local-policy
    from-address             *
    to-address               *
    source-realm             pstn
    description              "PSTN inbound to Five9 IVR"
    activate-time            N/A
    deactivate-time          N/A
    state                    enabled
    policy-attribute
        next-hop             SAG-Five9
        realm                five9
        action               replace-uri
        terminate-recursion  enabled
        carrier              ""
        cost                 1

; ========================================================
; POLICY 2: Five9 → Genesys (IVR transfer to agent)
; Calls from Five9 with target RP_* go to Genesys
; ========================================================
local-policy
    from-address             *
    to-address               sip:RP_*@*
    source-realm             five9
    description              "Five9 transfer to Genesys agent queues"
    activate-time            N/A
    deactivate-time          N/A
    state                    enabled
    policy-attribute
        next-hop             SAG-Genesys
        realm                genesys
        action               replace-uri
        terminate-recursion  enabled
        cost                 1
    ; Failover: if Genesys unreachable, return 503 to Five9
    policy-attribute
        next-hop             SAG-Five9
        realm                five9
        action               replace-uri
        terminate-recursion  enabled
        cost                 10

; ========================================================
; POLICY 3: Genesys → Five9 (Agent transfer back to Five9)
; For post-call survey or re-IVR scenarios
; ========================================================
local-policy
    from-address             *
    to-address               sip:Five9_*@*
    source-realm             genesys
    description              "Genesys transfer back to Five9"
    activate-time            N/A
    deactivate-time          N/A
    state                    enabled
    policy-attribute
        next-hop             SAG-Five9
        realm                five9
        action               replace-uri
        terminate-recursion  enabled
        cost                 1

; ========================================================
; POLICY 4: Genesys → PSTN (Outbound from Genesys agents)
; Normal outbound calls from Genesys agents
; ========================================================
local-policy
    from-address             *
    to-address               sip:+*@*
    source-realm             genesys
    description              "Genesys outbound to PSTN"
    activate-time            N/A
    deactivate-time          N/A
    state                    enabled
    policy-attribute
        next-hop             pstn-carrier
        realm                pstn
        action               replace-uri
        terminate-recursion  enabled
        cost                 1
```

### 3.10 SIP Manipulation (HMR) - Header Manipulation Rules

This is the critical section — normalizing headers between Five9 and Genesys.

```
ORACLE-SBC(configure)# session-router
ORACLE-SBC(session-router)# sip-manipulation

; ================================================================
; MANIPULATION RULESET 1: Five9 → Genesys (Outbound from Five9)
; Normalize Five9 X-headers to Bridge format for Genesys
; Preserve original ANI in P-Asserted-Identity
; ================================================================
sip-manipulation
    name                     five9-to-genesys-hmr
    description              "Normalize Five9 headers for Genesys consumption"

    header-rules
        name                 preserve-ani-pai
        header-name          P-Asserted-Identity
        action               manipulate
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "<sip:$HDR(X-Five9-ANI)@company.com>"

    header-rules
        name                 map-correlation-id
        header-name          X-Bridge-CorrelationId
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Five9-CorrelationId)"

    header-rules
        name                 map-intent
        header-name          X-Bridge-Intent
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Five9-Intent)"

    header-rules
        name                 map-custid
        header-name          X-Bridge-CustID
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Five9-CustID)"

    header-rules
        name                 map-language
        header-name          X-Bridge-Language
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Five9-Language)"

    header-rules
        name                 map-menuchoice
        header-name          X-Bridge-MenuChoice
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Five9-MenuChoice)"

    header-rules
        name                 map-priority
        header-name          X-Bridge-Priority
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Five9-Priority)"

    header-rules
        name                 map-transfer-target
        header-name          X-Bridge-TransferTarget
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Five9-TransferTarget)"

    header-rules
        name                 map-calluuid
        header-name          X-Bridge-CallUUID
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Five9-CallUUID)"

    header-rules
        name                 map-dnis
        header-name          X-Bridge-DNIS
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Five9-DNIS)"

    header-rules
        name                 map-timestamp
        header-name          X-Bridge-Timestamp
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Five9-Timestamp)"

    header-rules
        name                 map-balance
        header-name          X-Bridge-Balance
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Five9-Balance)"

    ; Remove original Five9 headers (topology hiding)
    header-rules
        name                 strip-five9-headers
        header-name          X-Five9-*
        action               delete
        comparison-type      pattern-rule
        msg-type             request
        methods              INVITE

    ; Rewrite Request-URI to Genesys Routing Point format
    header-rules
        name                 rewrite-ruri
        header-name          request-uri
        action               manipulate
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          "sip:(.*)@(.*)"
        new-value            "sip:$1@10.1.0.10:5060"


; ================================================================
; MANIPULATION RULESET 2: Genesys → Five9 (Transfer back)
; For reverse transfers (post-call survey, re-IVR)
; ================================================================
sip-manipulation
    name                     genesys-to-five9-hmr
    description              "Normalize Genesys headers for Five9 consumption"

    header-rules
        name                 map-gns-correlation
        header-name          X-Five9-CorrelationId
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Genesys-CorrelationId)"

    header-rules
        name                 map-gns-custid
        header-name          X-Five9-CustID
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Genesys-CustomerID)"

    header-rules
        name                 map-gns-intent
        header-name          X-Five9-Intent
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Genesys-Intent)"

    header-rules
        name                 map-gns-disposition
        header-name          X-Five9-Disposition
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Genesys-Disposition)"

    header-rules
        name                 map-gns-agentid
        header-name          X-Five9-AgentID
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "$HDR(X-Genesys-AgentID)"

    ; Strip Genesys-specific headers
    header-rules
        name                 strip-genesys-headers
        header-name          X-Genesys-*
        action               delete
        comparison-type      pattern-rule
        msg-type             request
        methods              INVITE


; ================================================================
; MANIPULATION RULESET 3: PSTN → Five9 (Inbound call routing)
; Add tracking header for inbound calls
; ================================================================
sip-manipulation
    name                     pstn-to-five9-hmr
    description              "Tag inbound PSTN calls for Five9"

    header-rules
        name                 add-source-tag
        header-name          X-Bridge-Source
        action               add
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
        match-value          ""
        new-value            "PSTN-Inbound"

    header-rules
        name                 preserve-pai
        header-name          P-Asserted-Identity
        action               store
        comparison-type      case-sensitive
        msg-type             request
        methods              INVITE
```

### 3.11 Apply Manipulation Rules to Session Agents

```
ORACLE-SBC(session-router)# session-agent

; Apply HMR to Five9 session agents (outbound manipulation = Five9→Genesys)
session-agent
    hostname                 five9-primary
    in-manipulationid        five9-to-genesys-hmr
    out-manipulationid       genesys-to-five9-hmr

session-agent
    hostname                 five9-secondary
    in-manipulationid        five9-to-genesys-hmr
    out-manipulationid       genesys-to-five9-hmr

; Apply HMR to Genesys session agents
session-agent
    hostname                 genesys-sip-primary
    in-manipulationid        genesys-to-five9-hmr
    out-manipulationid       five9-to-genesys-hmr

session-agent
    hostname                 genesys-sip-backup
    in-manipulationid        genesys-to-five9-hmr
    out-manipulationid       five9-to-genesys-hmr

; Apply HMR to PSTN carrier
session-agent
    hostname                 pstn-carrier
    in-manipulationid        pstn-to-five9-hmr
    out-manipulationid       ""
```

### 3.12 Media Manager (Anchored Media for Five9-in-Path)

Since Five9 must stay in the media path, we configure the SBC to **anchor media** (no direct RTP between Five9 and Genesys — SBC stays in middle).

```
ORACLE-SBC(configure)# media-manager
ORACLE-SBC(media-manager)# media-policy

; Media policy for Five9 realm
media-policy
    name                     media-policy-five9
    tos-values               46                  ; EF DSCP for voice
    media-type               audio
    in-media-type            audio

; Media policy for Genesys realm
media-policy
    name                     media-policy-genesys
    tos-values               46
    media-type               audio
    in-media-type            audio

; Steering pool (RTP port ranges)
ORACLE-SBC(media-manager)# steering-pool

; Five9-facing RTP ports
steering-pool
    ip-address               203.0.113.10
    start-port               10000
    end-port                 20000
    realm-id                 five9
    network-interface        external-net:0

; Genesys-facing RTP ports
steering-pool
    ip-address               10.1.0.50
    start-port               20001
    end-port                 40000
    realm-id                 genesys
    network-interface        internal-net:0

; Codec policy (ensure compatibility)
ORACLE-SBC(media-manager)# codec-policy

codec-policy
    name                     bridge-codec-policy
    allow-codecs
        name                 PCMU
        media-type           audio
    allow-codecs
        name                 PCMA
        media-type           audio
    allow-codecs
        name                 G729
        media-type           audio
    allow-codecs
        name                 telephone-event
        media-type           audio
    order-codecs             PCMU,PCMA,G729,telephone-event
    media-type-to-offer      audio
    dtmf-in-audio           disabled
```

### 3.13 Access Control Lists (ACLs)

```
ORACLE-SBC(configure)# session-router
ORACLE-SBC(session-router)# access-control

; Allow Five9 IP ranges
access-control
    realm-id                 five9
    description              "Five9 DC IP Ranges"
    source-address           <five9-dc1-subnet>/24
    destination-address      203.0.113.10
    application-protocol     SIP
    transport-protocol       TLS
    access                   permit
    average-rate-limit       100

access-control
    realm-id                 five9
    source-address           <five9-dc2-subnet>/24
    destination-address      203.0.113.10
    application-protocol     SIP
    transport-protocol       TLS
    access                   permit
    average-rate-limit       100

; Allow Genesys SIP Servers
access-control
    realm-id                 genesys
    description              "Genesys SIP Server HA Pair"
    source-address           10.1.0.10/32
    destination-address      10.1.0.50
    application-protocol     SIP
    transport-protocol       TCP
    access                   permit

access-control
    realm-id                 genesys
    source-address           10.1.0.11/32
    destination-address      10.1.0.50
    application-protocol     SIP
    transport-protocol       TCP
    access                   permit

; Allow PSTN Carrier
access-control
    realm-id                 pstn
    description              "PSTN Carrier SIP"
    source-address           198.51.100.0/24
    destination-address      203.0.113.10
    application-protocol     SIP
    transport-protocol       TCP
    access                   permit

; Deny all other
access-control
    realm-id                 five9
    source-address           0.0.0.0/0
    access                   deny
```

### 3.14 Session Constraints (Call Admission Control)

```
ORACLE-SBC(session-router)# session-constraints

session-constraints
    name                     five9-constraints
    max-sessions             200
    max-inbound-sessions     100
    max-outbound-sessions    200
    max-burst-rate           20          ; Max 20 new calls/second
    max-sustain-rate         10          ; Sustained 10 calls/second
    min-seizures             5
    min-asr                  30          ; Minimum 30% answer-seizure ratio

session-constraints
    name                     genesys-constraints
    max-sessions             500
    max-inbound-sessions     500
    max-outbound-sessions    200
    max-burst-rate           30
    max-sustain-rate         15
```

### 3.15 High Availability (Dual SBC)

```
ORACLE-SBC(configure)# system
ORACLE-SBC(system)# redundancy

redundancy
    state                    enabled
    type                     1+1
    peer                     203.0.113.11        ; SBC-B external IP
    priority                 200                  ; Higher = active
    health-score             100
    emergency-threshold      50
    advertisement-time       500                 ; ms
    percent-drift            10
```

### 3.16 SIP Options Ping (Health Monitoring)

```
ORACLE-SBC(session-router)# session-agent

; Five9 health monitoring
session-agent
    hostname                 five9-primary
    ping-method              OPTIONS
    ping-interval            30
    ping-in-service-response-codes  200
    ping-all-addresses       enabled
    out-service-503          enabled

; Genesys health monitoring
session-agent
    hostname                 genesys-sip-primary
    ping-method              OPTIONS
    ping-interval            15              ; More frequent for critical path
    ping-in-service-response-codes  200
    ping-all-addresses       enabled
    out-service-503          enabled
```



---

## 4. Genesys Configuration Server Objects

### 4.1 Object Hierarchy Overview

```
Configuration Server
│
├── Switch: SIPSwitch_Primary
│   │
│   ├── DN (Trunk Group): TRK_Five9_Bridge_In     [Inbound from Five9 via SBC]
│   ├── DN (Trunk Group): TRK_Five9_Bridge_Out    [Outbound back to Five9]
│   │
│   ├── DN (Routing Point): RP_Bridge_Entry        [Master entry point]
│   ├── DN (Routing Point): RP_Billing             [Billing queue entry]
│   ├── DN (Routing Point): RP_TechSupport         [Tech Support queue entry]
│   ├── DN (Routing Point): RP_Sales               [Sales queue entry]
│   ├── DN (Routing Point): RP_General             [General/Operator entry]
│   │
│   ├── DN (Virtual Queue): VQ_Billing             [Billing VQ for EWT]
│   ├── DN (Virtual Queue): VQ_TechSupport         [Tech Support VQ]
│   ├── DN (Virtual Queue): VQ_Sales               [Sales VQ]
│   ├── DN (Virtual Queue): VQ_General             [General VQ]
│   │
│   └── DN (ACD Queue): Existing queues...         [Pre-existing]
│
├── Application: SIPServer_Primary
├── Application: ORS_App_Bridge
├── Application: StatServer_Primary
│
├── Agent Group: AG_Billing
├── Agent Group: AG_TechSupport
├── Agent Group: AG_Sales
├── Agent Group: AG_General
│
├── Skill: Skill_Billing
├── Skill: Skill_TechSupport
├── Skill: Skill_Sales
├── Skill: Skill_General
├── Skill: Skill_English
├── Skill: Skill_Spanish
│
└── Transaction: Five9_Bridge_Context (for UserData keys)
```

### 4.2 Switch Object

```
┌─────────────────────────────────────────────────────────────────────┐
│ Object Type:    Switch                                               │
│ Name:           SIPSwitch_Primary                                    │
│ Type:           SIP Switch                                           │
│ TServer Link:   SIPServer_Primary                                    │
│                                                                     │
│ Options Tab:                                                         │
│   [General] section:                                                 │
│     switch-policy-on-no-answer-timeout = 30                          │
│                                                                     │
│ Annex Tab:                                                           │
│   [TServer] section:                                                 │
│     link-type = sipswitch                                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.3 Trunk Group DNs

#### 4.3.1 Inbound Trunk from Five9 (via SBC)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Object Type:    DN                                                    │
│ Switch:         SIPSwitch_Primary                                    │
│ Type:           Trunk Group                                          │
│ Number:         9100                                                 │
│ Name:           TRK_Five9_Bridge_In                                  │
│                                                                     │
│ Options Tab:                                                         │
│   capacity:           200                                            │
│   register:           false                                          │
│                                                                     │
│ Annex Tab:                                                           │
│   [TServer] section:                                                 │
│     contact:          sip:bridge@10.1.0.50:5060;transport=tcp        │
│     dn-type:          trunk                                          │
│     trunk-type:       inbound                                        │
│     destination:      RP_Bridge_Entry                                │
│     sip-accept-headers: X-Bridge-CorrelationId,X-Bridge-Intent,      │
│                         X-Bridge-CustID,X-Bridge-Language,           │
│                         X-Bridge-MenuChoice,X-Bridge-Priority,       │
│                         X-Bridge-TransferTarget,X-Bridge-CallUUID,   │
│                         X-Bridge-DNIS,X-Bridge-Timestamp,            │
│                         X-Bridge-Balance                             │
│                                                                     │
│   [Five9Bridge] section (custom documentation):                      │
│     description:      "Inbound trunk from Five9 via Oracle SBC"      │
│     peer-ip:          10.1.0.50 (SBC internal IP)                    │
│     peer-port:        5060                                           │
│     protocol:         TCP                                            │
└─────────────────────────────────────────────────────────────────────┘
```

#### 4.3.2 Outbound Trunk to Five9 (for reverse transfers)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Object Type:    DN                                                    │
│ Switch:         SIPSwitch_Primary                                    │
│ Type:           Trunk Group                                          │
│ Number:         9200                                                 │
│ Name:           TRK_Five9_Bridge_Out                                 │
│                                                                     │
│ Options Tab:                                                         │
│   capacity:           100                                            │
│   register:           false                                          │
│                                                                     │
│ Annex Tab:                                                           │
│   [TServer] section:                                                 │
│     contact:          sip:Five9_Survey@10.1.0.50:5060;transport=tcp  │
│     dn-type:          trunk                                          │
│     trunk-type:       outbound                                       │
│                                                                     │
│   [Five9Bridge] section:                                             │
│     description:      "Outbound trunk to Five9 for surveys/re-IVR"   │
│     peer-ip:          10.1.0.50 (SBC internal IP)                    │
│     peer-port:        5060                                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.4 Routing Point DNs

#### 4.4.1 Master Bridge Entry Point

```
┌─────────────────────────────────────────────────────────────────────┐
│ Object Type:    DN                                                    │
│ Switch:         SIPSwitch_Primary                                    │
│ Type:           Routing Point                                        │
│ Number:         RP_Bridge_Entry                                      │
│ Name:           RP_Bridge_Entry                                      │
│                                                                     │
│ Options Tab:                                                         │
│   register:           false                                          │
│                                                                     │
│ Annex Tab:                                                           │
│   [TServer] section:                                                 │
│     dn-type:          routing-point                                  │
│     associated-application: ORS_App_Bridge                           │
│     sip-cti-control:  talk,hold,retrieve,redirect,complete-transfer  │
│     propagate-user-data: true                                        │
│                                                                     │
│   [routing] section:                                                 │
│     default-destination: RP_General                                  │
│     timeout:          10                                             │
│                                                                     │
│ Strategy Assignment:                                                 │
│   Default Strategy:   Bridge_Master_Router_v1                        │
│   (Composer app that reads X-headers and dispatches)                 │
└─────────────────────────────────────────────────────────────────────┘
```

#### 4.4.2 Billing Routing Point

```
┌─────────────────────────────────────────────────────────────────────┐
│ Object Type:    DN                                                    │
│ Switch:         SIPSwitch_Primary                                    │
│ Type:           Routing Point                                        │
│ Number:         RP_Billing                                           │
│ Name:           RP_Billing                                           │
│                                                                     │
│ Annex Tab:                                                           │
│   [TServer] section:                                                 │
│     dn-type:          routing-point                                  │
│     associated-application: ORS_App_Bridge                           │
│     propagate-user-data: true                                        │
│                                                                     │
│   [routing] section:                                                 │
│     target-agent-group: AG_Billing                                   │
│     target-skill:     Skill_Billing                                  │
│     virtual-queue:    VQ_Billing                                     │
│                                                                     │
│ Strategy Assignment:                                                 │
│   Default Strategy:   Bridge_Billing_Strategy_v1                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### 4.4.3 Technical Support Routing Point

```
┌─────────────────────────────────────────────────────────────────────┐
│ Object Type:    DN                                                    │
│ Switch:         SIPSwitch_Primary                                    │
│ Type:           Routing Point                                        │
│ Number:         RP_TechSupport                                       │
│ Name:           RP_TechSupport                                       │
│                                                                     │
│ Annex Tab:                                                           │
│   [TServer] section:                                                 │
│     dn-type:          routing-point                                  │
│     associated-application: ORS_App_Bridge                           │
│     propagate-user-data: true                                        │
│                                                                     │
│   [routing] section:                                                 │
│     target-agent-group: AG_TechSupport                               │
│     target-skill:     Skill_TechSupport                              │
│     virtual-queue:    VQ_TechSupport                                 │
│                                                                     │
│ Strategy Assignment:                                                 │
│   Default Strategy:   Bridge_TechSupport_Strategy_v1                 │
└─────────────────────────────────────────────────────────────────────┘
```

#### 4.4.4 Sales Routing Point

```
┌─────────────────────────────────────────────────────────────────────┐
│ Object Type:    DN                                                    │
│ Switch:         SIPSwitch_Primary                                    │
│ Type:           Routing Point                                        │
│ Number:         RP_Sales                                             │
│ Name:           RP_Sales                                             │
│                                                                     │
│ Annex Tab:                                                           │
│   [TServer] section:                                                 │
│     dn-type:          routing-point                                  │
│     associated-application: ORS_App_Bridge                           │
│     propagate-user-data: true                                        │
│                                                                     │
│   [routing] section:                                                 │
│     target-agent-group: AG_Sales                                     │
│     target-skill:     Skill_Sales                                    │
│     virtual-queue:    VQ_Sales                                       │
│                                                                     │
│ Strategy Assignment:                                                 │
│   Default Strategy:   Bridge_Sales_Strategy_v1                       │
└─────────────────────────────────────────────────────────────────────┘
```

#### 4.4.5 General/Operator Routing Point

```
┌─────────────────────────────────────────────────────────────────────┐
│ Object Type:    DN                                                    │
│ Switch:         SIPSwitch_Primary                                    │
│ Type:           Routing Point                                        │
│ Number:         RP_General                                           │
│ Name:           RP_General                                           │
│                                                                     │
│ Annex Tab:                                                           │
│   [TServer] section:                                                 │
│     dn-type:          routing-point                                  │
│     associated-application: ORS_App_Bridge                           │
│     propagate-user-data: true                                        │
│                                                                     │
│   [routing] section:                                                 │
│     target-agent-group: AG_General                                   │
│     target-skill:     Skill_General                                  │
│     virtual-queue:    VQ_General                                     │
│                                                                     │
│ Strategy Assignment:                                                 │
│   Default Strategy:   Bridge_General_Strategy_v1                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.5 Virtual Queue DNs

```
┌─────────────────────────────────────────────────────────────────────┐
│ VQ_Billing                                                           │
│   Switch:       SIPSwitch_Primary                                    │
│   Type:         Virtual Queue                                        │
│   Number:       VQ_Billing                                           │
│   Stat Server:  StatServer_Primary                                   │
│   Queue:        ACD_Billing (link to existing ACD queue)             │
│                                                                     │
│ VQ_TechSupport                                                       │
│   Switch:       SIPSwitch_Primary                                    │
│   Type:         Virtual Queue                                        │
│   Number:       VQ_TechSupport                                       │
│   Queue:        ACD_TechSupport                                      │
│                                                                     │
│ VQ_Sales                                                             │
│   Switch:       SIPSwitch_Primary                                    │
│   Type:         Virtual Queue                                        │
│   Number:       VQ_Sales                                             │
│   Queue:        ACD_Sales                                            │
│                                                                     │
│ VQ_General                                                           │
│   Switch:       SIPSwitch_Primary                                    │
│   Type:         Virtual Queue                                        │
│   Number:       VQ_General                                           │
│   Queue:        ACD_General                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.6 SIP Server Application Configuration

```
┌─────────────────────────────────────────────────────────────────────┐
│ Application Name:   SIPServer_Primary                                │
│ Type:               SIPServer                                        │
│ Host:               genesys-sip-host1                                │
│ Port:               5060                                             │
│ Backup Server:      SIPServer_Backup (HA pair)                       │
│                                                                     │
│ ═══════════════════════════════════════════════════════════════════   │
│ OPTIONS TAB                                                          │
│ ═══════════════════════════════════════════════════════════════════   │
│                                                                     │
│ [TServer] section:                                                   │
│   router-timeout             = 10                                    │
│   default-dn                 = RP_General                            │
│   sip-cti-control            = talk,hold,retrieve,redirect,          │
│                                complete-transfer,init-transfer,       │
│                                single-step-transfer                  │
│   user-data-propagation      = all                                   │
│   sip-header-x-bridge        = propagate                             │
│                                                                     │
│ [SIP] section:                                                       │
│   transport-type-outbound    = tcp                                   │
│   route-local-calls-via-proxy = false                                │
│   max-sessions               = 500                                   │
│   sip-session-expires        = 1800                                  │
│   sip-min-se                 = 90                                    │
│                                                                     │
│ [sip-headers] section:                                               │
│   ; Accept and propagate X-Bridge-* headers from SBC                 │
│   x-bridge-correlationid     = propagate,attach                      │
│   x-bridge-intent            = propagate,attach                      │
│   x-bridge-custid            = propagate,attach                      │
│   x-bridge-language          = propagate,attach                      │
│   x-bridge-menuchoice        = propagate,attach                      │
│   x-bridge-priority          = propagate,attach                      │
│   x-bridge-transfertarget    = propagate,attach                      │
│   x-bridge-calluuid          = propagate,attach                      │
│   x-bridge-dnis              = propagate,attach                      │
│   x-bridge-timestamp         = propagate,attach                      │
│   x-bridge-balance           = propagate,attach                      │
│                                                                     │
│ [SIP-Header-To-UserData-Mapping] section:                            │
│   ; Map incoming X-Bridge headers to Genesys UserData KVPs          │
│   X-Bridge-CorrelationId    = Bridge_CorrelationId                   │
│   X-Bridge-Intent           = Bridge_Intent                          │
│   X-Bridge-CustID           = Bridge_CustomerID                      │
│   X-Bridge-Language         = Bridge_Language                        │
│   X-Bridge-MenuChoice       = Bridge_MenuChoice                      │
│   X-Bridge-Priority         = Bridge_Priority                        │
│   X-Bridge-TransferTarget   = Bridge_TransferTarget                  │
│   X-Bridge-CallUUID         = Bridge_Five9CallUUID                   │
│   X-Bridge-DNIS             = Bridge_DNIS                            │
│   X-Bridge-Timestamp        = Bridge_IVRTimestamp                    │
│   X-Bridge-Balance          = Bridge_AccountBalance                  │
│                                                                     │
│ [UserData-To-SIP-Header-Mapping] section:                            │
│   ; Map Genesys UserData back to SIP headers (for reverse transfer)  │
│   Bridge_CorrelationId      = X-Genesys-CorrelationId                │
│   Bridge_CustomerID         = X-Genesys-CustomerID                   │
│   Bridge_Intent             = X-Genesys-Intent                       │
│   Genesys_Disposition       = X-Genesys-Disposition                  │
│   Genesys_AgentID           = X-Genesys-AgentID                      │
│   Genesys_HandleTime        = X-Genesys-HandleTime                   │
│                                                                     │
│ [SIP-PAI] section:                                                   │
│   ; Use P-Asserted-Identity for ANI (preserves original caller)      │
│   use-pai-for-ani           = true                                   │
│   pai-format                = tel                                    │
│                                                                     │
│ [call-control] section:                                              │
│   hold-treatment            = music-on-hold                          │
│   transfer-complete-timeout = 30                                     │
│   no-answer-timeout         = 30                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.7 ORS Application Object

```
┌─────────────────────────────────────────────────────────────────────┐
│ Application Name:   ORS_App_Bridge                                   │
│ Type:               SCXML Application (Orchestration Server)         │
│ Host:               genesys-ors-host1                                │
│ Port:               8080                                             │
│ Backup:             ORS_App_Bridge_Backup                            │
│                                                                     │
│ OPTIONS TAB                                                          │
│                                                                     │
│ [general] section:                                                   │
│   application-path           = /Bridge_Master_Router                 │
│   content-server-url         = http://composer-server:8888           │
│                                                                     │
│ [scxml-engine] section:                                              │
│   max-sessions               = 300                                   │
│   session-timeout            = 120                                   │
│                                                                     │
│ [http-client] section:                                               │
│   ; For External Service blocks (calls to GCP middleware)            │
│   connect-timeout            = 5000                                  │
│   socket-timeout             = 10000                                 │
│   max-connections-per-host   = 50                                    │
│   max-total-connections      = 200                                   │
│                                                                     │
│ Connections Tab:                                                     │
│   SIPServer_Primary          (port: 5060)                            │
│   StatServer_Primary         (port: 5040)                            │
│   URS_Primary                (port: 8070)                            │
│   ConfigServer_Primary       (port: 2020)                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.8 Transaction Object (UserData Schema)

Defines the allowed UserData keys for the bridge interaction:

```
┌─────────────────────────────────────────────────────────────────────┐
│ Object Type:    Transaction                                          │
│ Name:           Five9_Bridge_Context                                  │
│ Type:           voice                                                │
│                                                                     │
│ User Data Keys:                                                      │
│ ┌────────────────────────┬──────────┬──────────────────────────────┐ │
│ │ Key Name               │ Type     │ Description                  │ │
│ ├────────────────────────┼──────────┼──────────────────────────────┤ │
│ │ Bridge_CorrelationId   │ String   │ Cross-platform UUID          │ │
│ │ Bridge_Intent          │ String   │ IVR intent (billing, sales)  │ │
│ │ Bridge_CustomerID      │ String   │ Authenticated customer ID    │ │
│ │ Bridge_Language        │ String   │ Language selected (en/es)    │ │
│ │ Bridge_MenuChoice      │ String   │ IVR menu option (1-9)        │ │
│ │ Bridge_Priority        │ String   │ Priority level               │ │
│ │ Bridge_TransferTarget  │ String   │ Intended Genesys target RP   │ │
│ │ Bridge_Five9CallUUID   │ String   │ Five9 session ID             │ │
│ │ Bridge_DNIS            │ String   │ Original DNIS dialed         │ │
│ │ Bridge_IVRTimestamp    │ String   │ IVR entry time (ISO 8601)    │ │
│ │ Bridge_AccountBalance  │ String   │ Account balance if checked   │ │
│ │ Bridge_Source          │ String   │ "Five9_IVR"                  │ │
│ │ Bridge_IVRDuration     │ String   │ Seconds spent in IVR         │ │
│ │ Genesys_Disposition    │ String   │ Agent disposition code       │ │
│ │ Genesys_AgentID        │ String   │ Handling agent ID            │ │
│ │ Genesys_HandleTime     │ String   │ Agent handle time            │ │
│ │ Genesys_QueueTime      │ String   │ Time in Genesys queue        │ │
│ └────────────────────────┴──────────┴──────────────────────────────┘ │
│                                                                     │
│ Propagation: All keys propagated on transfer/consultation            │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.9 Business Attribute (for Interaction Type Tracking)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Object Type:    Business Attribute                                    │
│ Name:           Five9_Bridge_Interactions                             │
│                                                                     │
│ Attribute Values:                                                    │
│   - Five9_IVR_Transfer     (calls transferred from Five9 IVR)        │
│   - Five9_Self_Service     (calls completed on Five9)                │
│   - Five9_Callback         (callbacks scheduled from Five9)          │
│   - Genesys_To_Five9       (calls transferred back to Five9)         │
│                                                                     │
│ Used in: Interaction Routing Designer, Info Mart reporting           │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.10 Stat Server Configuration (for EWT/Agent Status)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Application Name:   StatServer_Primary                               │
│                                                                     │
│ OPTIONS TAB:                                                         │
│                                                                     │
│ [statserver] section:                                                │
│   ; Ensure bridge-related interactions are tracked                   │
│   external-interaction-type  = Five9_Bridge                          │
│                                                                     │
│ [VirtualQueue] section:                                              │
│   ; Configure stats for bridge virtual queues                        │
│   vq-ewt-algorithm          = PeriodTime                            │
│   vq-ewt-period             = 900                                   │
│                                                                     │
│ Statistics to monitor (via Stat Server requests from ORS):           │
│   - CurrNumberWaiting (per queue)                                   │
│   - CurrentEstimatedWaitTime (per VQ)                                │
│   - AgentsLoggedIn (per Agent Group)                                 │
│   - AgentsReady (per Agent Group)                                    │
└─────────────────────────────────────────────────────────────────────┘
```



---

## 5. ORS/Composer Routing Strategy

### 5.1 Strategy Architecture

The **Bridge_Master_Router** strategy is assigned to `RP_Bridge_Entry`. It:
1. Reads X-Bridge-* headers (already mapped to UserData by SIP Server)
2. Calls GCP middleware to get full context (enrichment)
3. Attaches all context as UserData
4. Routes to the correct sub-Routing Point based on intent/transfer target
5. Handles fallback if target queue has no agents

### 5.2 Composer Workflow: Bridge_Master_Router

```xml
<?xml version="1.0" encoding="UTF-8"?>
<scxml xmlns="http://www.w3.org/2005/07/scxml" version="1.0" 
       initial="Entry" name="Bridge_Master_Router">

  <!-- ============================================================ -->
  <!-- ENTRY: Call arrives from Five9 via SBC                        -->
  <!-- UserData already populated by SIP Server header mapping       -->
  <!-- ============================================================ -->
  <state id="Entry">
    <onentry>
      <log label="Bridge_Router" 
           expr="'Call arrived from Five9. CorrelationId=' + 
                  UserData.Bridge_CorrelationId + 
                  ' Intent=' + UserData.Bridge_Intent"/>
    </onentry>
    <transition target="ValidateHeaders"/>
  </state>

  <!-- ============================================================ -->
  <!-- VALIDATE: Ensure critical headers are present                 -->
  <!-- ============================================================ -->
  <state id="ValidateHeaders">
    <transition target="FetchFullContext" 
                cond="UserData.Bridge_CorrelationId != '' AND 
                      UserData.Bridge_CorrelationId != null"/>
    <!-- If no correlation ID, treat as generic call -->
    <transition target="DefaultRouting"/>
  </state>

  <!-- ============================================================ -->
  <!-- FETCH FULL CONTEXT: Call GCP middleware for enriched data      -->
  <!-- ============================================================ -->
  <state id="FetchFullContext">
    <onentry>
      <!-- External Service Block: HTTP GET to GCP middleware -->
      <send event="http.request" target="ExternalService">
        <param name="method" value="GET"/>
        <param name="url" 
               value="'https://bridge-api-xxxxx.run.app/api/v1/context/' + 
                       UserData.Bridge_CorrelationId"/>
        <param name="headers" value="{'Authorization': 'Bearer ${GCP_TOKEN}',
                                       'Content-Type': 'application/json'}"/>
        <param name="timeout" value="5000"/>
      </send>
    </onentry>

    <!-- Success: middleware returned full context -->
    <transition event="http.response.200" target="EnrichUserData">
      <assign name="MiddlewareResponse" expr="_event.data.body"/>
    </transition>

    <!-- Timeout/Error: proceed with SIP headers only (graceful degradation) -->
    <transition event="http.response.*" target="RouteByHeaders">
      <log label="Bridge_Router" 
           expr="'Middleware unavailable. Routing by SIP headers only.'"/>
    </transition>
    <transition event="error.*" target="RouteByHeaders"/>
  </state>

  <!-- ============================================================ -->
  <!-- ENRICH USER DATA: Merge middleware response into UserData      -->
  <!-- ============================================================ -->
  <state id="EnrichUserData">
    <onentry>
      <!-- Attach additional data from middleware that wasn't in headers -->
      <assign name="UserData.Bridge_CustomerName" 
              expr="MiddlewareResponse.customerName"/>
      <assign name="UserData.Bridge_AccountType" 
              expr="MiddlewareResponse.accountType"/>
      <assign name="UserData.Bridge_LastInteraction" 
              expr="MiddlewareResponse.lastInteractionDate"/>
      <assign name="UserData.Bridge_CustomerSegment" 
              expr="MiddlewareResponse.customerSegment"/>
      <assign name="UserData.Bridge_OpenCases" 
              expr="MiddlewareResponse.openCaseCount"/>
      <assign name="UserData.Bridge_IVRDuration" 
              expr="MiddlewareResponse.ivrDuration"/>
      
      <!-- Mark source for reporting -->
      <assign name="UserData.Bridge_Source" expr="'Five9_IVR'"/>

      <log label="Bridge_Router" 
           expr="'Context enriched. CustomerName=' + 
                  UserData.Bridge_CustomerName + 
                  ' Segment=' + UserData.Bridge_CustomerSegment"/>
    </onentry>
    <transition target="RouteByHeaders"/>
  </state>

  <!-- ============================================================ -->
  <!-- ROUTE BY HEADERS: Determine destination based on intent       -->
  <!-- ============================================================ -->
  <state id="RouteByHeaders">
    <onentry>
      <!-- Determine target Routing Point from TransferTarget header -->
      <assign name="TargetRP" expr="UserData.Bridge_TransferTarget"/>
      
      <!-- Set priority based on Five9 priority flag -->
      <if cond="UserData.Bridge_Priority == 'high'">
        <assign name="InteractionPriority" expr="8"/>
      <elseif cond="UserData.Bridge_Priority == 'normal'"/>
        <assign name="InteractionPriority" expr="5"/>
      <else/>
        <assign name="InteractionPriority" expr="3"/>
      </if>

      <!-- Set language skill requirement -->
      <if cond="UserData.Bridge_Language == 'es'">
        <assign name="LanguageSkill" expr="'Skill_Spanish'"/>
      <else/>
        <assign name="LanguageSkill" expr="'Skill_English'"/>
      </if>
    </onentry>

    <!-- Route based on TransferTarget value -->
    <transition target="RouteToBilling" 
                cond="TargetRP == 'RP_Billing'"/>
    <transition target="RouteToTechSupport" 
                cond="TargetRP == 'RP_TechSupport'"/>
    <transition target="RouteToSales" 
                cond="TargetRP == 'RP_Sales'"/>
    <transition target="RouteToGeneral" 
                cond="TargetRP == 'RP_General'"/>
    
    <!-- Fallback: route by intent if TransferTarget is missing -->
    <transition target="RouteByIntent"/>
  </state>

  <!-- ============================================================ -->
  <!-- ROUTE BY INTENT: Fallback if TransferTarget not available     -->
  <!-- ============================================================ -->
  <state id="RouteByIntent">
    <transition target="RouteToBilling" 
                cond="UserData.Bridge_Intent == 'billing' OR 
                      UserData.Bridge_Intent == 'balance_then_agent'"/>
    <transition target="RouteToTechSupport" 
                cond="UserData.Bridge_Intent == 'technical_support'"/>
    <transition target="RouteToSales" 
                cond="UserData.Bridge_Intent == 'sales'"/>
    <transition target="RouteToGeneral" 
                cond="UserData.Bridge_Intent == 'operator'"/>
    <!-- Default fallback -->
    <transition target="RouteToGeneral"/>
  </state>

  <!-- ============================================================ -->
  <!-- BILLING ROUTE                                                  -->
  <!-- ============================================================ -->
  <state id="RouteToBilling">
    <onentry>
      <log label="Bridge_Router" expr="'Routing to Billing queue'"/>
      <send event="route.request">
        <param name="target_type" value="agent_group"/>
        <param name="target" value="AG_Billing"/>
        <param name="priority" value="InteractionPriority"/>
        <param name="required_skills" 
               value="[{'skill': 'Skill_Billing', 'level': 5}, 
                        {'skill': LanguageSkill, 'level': 3}]"/>
        <param name="virtual_queue" value="VQ_Billing"/>
        <param name="timeout" value="60"/>
        <param name="treatment" value="music_billing_hold"/>
      </send>
    </onentry>
    <transition event="route.done" target="PostRouteUpdate"/>
    <transition event="route.failed" target="RouteOverflow"/>
  </state>

  <!-- ============================================================ -->
  <!-- TECH SUPPORT ROUTE                                             -->
  <!-- ============================================================ -->
  <state id="RouteToTechSupport">
    <onentry>
      <log label="Bridge_Router" expr="'Routing to TechSupport queue'"/>
      <send event="route.request">
        <param name="target_type" value="agent_group"/>
        <param name="target" value="AG_TechSupport"/>
        <param name="priority" value="InteractionPriority"/>
        <param name="required_skills" 
               value="[{'skill': 'Skill_TechSupport', 'level': 5}, 
                        {'skill': LanguageSkill, 'level': 3}]"/>
        <param name="virtual_queue" value="VQ_TechSupport"/>
        <param name="timeout" value="90"/>
        <param name="treatment" value="music_tech_hold"/>
      </send>
    </onentry>
    <transition event="route.done" target="PostRouteUpdate"/>
    <transition event="route.failed" target="RouteOverflow"/>
  </state>

  <!-- ============================================================ -->
  <!-- SALES ROUTE (higher priority)                                  -->
  <!-- ============================================================ -->
  <state id="RouteToSales">
    <onentry>
      <log label="Bridge_Router" expr="'Routing to Sales queue'"/>
      <send event="route.request">
        <param name="target_type" value="agent_group"/>
        <param name="target" value="AG_Sales"/>
        <param name="priority" value="8"/>
        <param name="required_skills" 
               value="[{'skill': 'Skill_Sales', 'level': 5}, 
                        {'skill': LanguageSkill, 'level': 3}]"/>
        <param name="virtual_queue" value="VQ_Sales"/>
        <param name="timeout" value="45"/>
        <param name="treatment" value="music_sales_hold"/>
      </send>
    </onentry>
    <transition event="route.done" target="PostRouteUpdate"/>
    <transition event="route.failed" target="RouteOverflow"/>
  </state>

  <!-- ============================================================ -->
  <!-- GENERAL/OPERATOR ROUTE                                         -->
  <!-- ============================================================ -->
  <state id="RouteToGeneral">
    <onentry>
      <log label="Bridge_Router" expr="'Routing to General queue'"/>
      <send event="route.request">
        <param name="target_type" value="agent_group"/>
        <param name="target" value="AG_General"/>
        <param name="priority" value="InteractionPriority"/>
        <param name="required_skills" 
               value="[{'skill': 'Skill_General', 'level': 1}, 
                        {'skill': LanguageSkill, 'level': 3}]"/>
        <param name="virtual_queue" value="VQ_General"/>
        <param name="timeout" value="60"/>
        <param name="treatment" value="music_general_hold"/>
      </send>
    </onentry>
    <transition event="route.done" target="PostRouteUpdate"/>
    <transition event="route.failed" target="RouteOverflow"/>
  </state>

  <!-- ============================================================ -->
  <!-- OVERFLOW: All agents busy or target unavailable                -->
  <!-- ============================================================ -->
  <state id="RouteOverflow">
    <onentry>
      <log label="Bridge_Router" 
           expr="'Primary route failed. Trying overflow to AG_General'"/>
      <!-- Try general pool as overflow -->
      <send event="route.request">
        <param name="target_type" value="agent_group"/>
        <param name="target" value="AG_General"/>
        <param name="priority" value="9"/>
        <param name="timeout" value="120"/>
      </send>
    </onentry>
    <transition event="route.done" target="PostRouteUpdate"/>
    <transition event="route.failed" target="GenesysUnavailable"/>
  </state>

  <!-- ============================================================ -->
  <!-- GENESYS UNAVAILABLE: Return 503 to SBC/Five9                  -->
  <!-- Five9 IVR script handles failover (keep in queue/callback)    -->
  <!-- ============================================================ -->
  <state id="GenesysUnavailable">
    <onentry>
      <log label="Bridge_Router" level="error" 
           expr="'All Genesys agents unavailable. Returning 503.'"/>
      <!-- Send 503 back to Five9 via SBC -->
      <send event="route.reject">
        <param name="reason" value="503"/>
        <param name="message" value="Service Unavailable - No Agents"/>
      </send>
    </onentry>
    <transition target="Exit"/>
  </state>

  <!-- ============================================================ -->
  <!-- POST-ROUTE UPDATE: Notify middleware of successful routing     -->
  <!-- ============================================================ -->
  <state id="PostRouteUpdate">
    <onentry>
      <!-- Notify GCP middleware that call was routed successfully -->
      <send event="http.request" target="ExternalService">
        <param name="method" value="POST"/>
        <param name="url" 
               value="'https://bridge-api-xxxxx.run.app/api/v1/routed'"/>
        <param name="body" 
               value="{'correlationId': UserData.Bridge_CorrelationId,
                        'status': 'routed_to_agent',
                        'genesysQueue': TargetRP,
                        'routedTimestamp': system.timestamp,
                        'agentGroup': RouteResult.targetAgent}"/>
        <param name="timeout" value="3000"/>
      </send>
    </onentry>
    <!-- Don't wait for response, fire-and-forget -->
    <transition target="Exit"/>
  </state>

  <!-- ============================================================ -->
  <!-- DEFAULT ROUTING: No Five9 headers, treat as normal call       -->
  <!-- ============================================================ -->
  <state id="DefaultRouting">
    <onentry>
      <log label="Bridge_Router" 
           expr="'No Bridge headers found. Default routing.'"/>
      <send event="route.default"/>
    </onentry>
    <transition target="Exit"/>
  </state>

  <final id="Exit"/>
</scxml>
```

### 5.3 Composer Block Layout (Visual Representation)

```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│  [Entry] ──► [Log Block] ──► [Branching: Headers Present?]            │
│                                    │              │                    │
│                                   YES             NO                   │
│                                    │              │                    │
│                                    ▼              ▼                    │
│                          [External Service]   [Default Route]         │
│                          (GET middleware)      (RP_General)            │
│                                    │                                   │
│                                    ▼                                   │
│                          [User Data Block]                             │
│                          (Enrich context)                              │
│                                    │                                   │
│                                    ▼                                   │
│                          [Set Priority Variable]                       │
│                                    │                                   │
│                                    ▼                                   │
│                          [Branching: TransferTarget?]                  │
│                           │      │      │      │                      │
│                      Billing  Tech   Sales  General                   │
│                           │      │      │      │                      │
│                           ▼      ▼      ▼      ▼                      │
│                        [Target Blocks - Skills-based routing]          │
│                           │      │      │      │                      │
│                           └──────┴──────┴──────┘                      │
│                                    │                                   │
│                              On Success                                │
│                                    │                                   │
│                                    ▼                                   │
│                          [External Service]                            │
│                          (POST /routed notification)                   │
│                                    │                                   │
│                                    ▼                                   │
│                                 [Exit]                                 │
│                                                                        │
│                              On Failure                                 │
│                                    │                                   │
│                                    ▼                                   │
│                          [Overflow Target]                             │
│                          (AG_General, priority 9)                      │
│                                    │                                   │
│                              On Failure                                 │
│                                    │                                   │
│                                    ▼                                   │
│                          [Reject: 503]                                 │
│                          (Five9 handles failover)                      │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 5.4 Agent Desktop Screen Pop Configuration

When the call is delivered to an agent, Genesys Workspace Desktop (or Interaction Workspace) displays the Bridge context:

```
Workspace Desktop > Interaction Bar > Case Information

┌─────────────────────────────────────────────────────────────────────┐
│ SCREEN POP CONFIGURATION (Interaction Workspace)                     │
│                                                                     │
│ Configuration Layer > interaction-workspace > interaction.case-data  │
│                                                                     │
│ Section: Five9_Bridge_Context                                        │
│   Display Name: "Five9 IVR Context"                                  │
│   Visibility: Always (when Bridge_Source = "Five9_IVR")              │
│                                                                     │
│ Fields:                                                              │
│ ┌──────────────────────┬──────────────────┬────────────────────────┐ │
│ │ UserData Key         │ Display Label    │ Read-Only?             │ │
│ ├──────────────────────┼──────────────────┼────────────────────────┤ │
│ │ Bridge_CorrelationId │ Correlation ID   │ Yes                    │ │
│ │ Bridge_CustomerID    │ Customer ID      │ Yes                    │ │
│ │ Bridge_CustomerName  │ Customer Name    │ Yes                    │ │
│ │ Bridge_Intent        │ Caller Intent    │ Yes                    │ │
│ │ Bridge_Language      │ Language         │ Yes                    │ │
│ │ Bridge_MenuChoice    │ IVR Selection    │ Yes                    │ │
│ │ Bridge_AccountBalance│ Acct Balance     │ Yes                    │ │
│ │ Bridge_Priority      │ Priority         │ Yes                    │ │
│ │ Bridge_DNIS          │ Number Dialed    │ Yes                    │ │
│ │ Bridge_Five9CallUUID │ Five9 Call ID    │ Yes                    │ │
│ │ Bridge_IVRTimestamp  │ IVR Entry Time   │ Yes                    │ │
│ │ Bridge_Source        │ Source Platform   │ Yes                    │ │
│ └──────────────────────┴──────────────────┴────────────────────────┘ │
│                                                                     │
│ URL Pop (optional):                                                  │
│   URL: https://crm.company.com/customer/{Bridge_CustomerID}          │
│   Condition: Bridge_CustomerID IS NOT NULL                           │
│   Target: Embedded Browser panel                                     │
└─────────────────────────────────────────────────────────────────────┘
```



---

## 6. GCP Cloud Run Middleware API (Data Bridge)

### 6.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    GCP PROJECT: contact-center-bridge                    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                 CLOUD RUN: bridge-api                            │   │
│  │                                                                 │   │
│  │  Endpoints:                                                     │   │
│  │    POST /api/v1/pre-transfer    (Five9 → store context)         │   │
│  │    GET  /api/v1/context/{id}    (Genesys ORS → fetch context)   │   │
│  │    POST /api/v1/routed          (Genesys ORS → update status)   │   │
│  │    POST /api/v1/completed       (Post-call → final update)      │   │
│  │    POST /api/v1/reverse-transfer (Genesys → Five9 context)      │   │
│  │    GET  /api/v1/health          (Health check)                  │   │
│  │                                                                 │   │
│  │  Runtime: Node.js 20 / Python 3.12                              │   │
│  │  Memory: 512 MB                                                 │   │
│  │  Min Instances: 2 (always warm)                                 │   │
│  │  Max Instances: 20                                              │   │
│  │  Concurrency: 80                                                │   │
│  │  Timeout: 30s                                                   │   │
│  └──────────────────────┬──────────────────────────────────────────┘   │
│                          │                                              │
│           ┌──────────────┼──────────────┐                              │
│           │              │              │                              │
│           ▼              ▼              ▼                              │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐                   │
│  │ Firestore  │  │  Pub/Sub    │  │  BigQuery    │                   │
│  │ (context   │  │  (events    │  │  (analytics  │                   │
│  │  store)    │  │   stream)   │  │   reporting) │                   │
│  └────────────┘  └─────────────┘  └──────────────┘                   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Secret Manager: API keys, Five9 creds, service account tokens  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 API Specification (OpenAPI 3.0)

```yaml
openapi: "3.0.3"
info:
  title: Five9-Genesys Bridge API
  version: "1.0.0"
  description: |
    Middleware service providing data bridge and correlation between
    Five9 IVR and Genesys Engage agent platform.

servers:
  - url: https://bridge-api-xxxxx.run.app
    description: Production (Cloud Run)

security:
  - bearerAuth: []

paths:
  /api/v1/pre-transfer:
    post:
      summary: Store call context before Five9 transfers to Genesys
      description: |
        Called by Five9 IVR script (HTTP module) immediately before
        initiating SIP transfer. Stores full call context and returns
        confirmation with correlation ID.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PreTransferRequest'
      responses:
        '200':
          description: Context stored successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PreTransferResponse'
        '400':
          description: Invalid request
        '500':
          description: Internal server error

  /api/v1/context/{correlationId}:
    get:
      summary: Retrieve full call context by correlation ID
      description: |
        Called by Genesys ORS (External Service block) when the
        transferred call arrives. Returns enriched context for
        routing decisions and agent screen pop.
      parameters:
        - name: correlationId
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Context found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CallContext'
        '404':
          description: Context not found (expired or invalid ID)
        '500':
          description: Internal server error

  /api/v1/routed:
    post:
      summary: Update context after Genesys successfully routes call
      description: |
        Called by Genesys ORS after the call is delivered to an agent.
        Updates the context record with routing details.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RoutedNotification'
      responses:
        '200':
          description: Context updated
        '404':
          description: Correlation ID not found

  /api/v1/completed:
    post:
      summary: Mark call as completed with final disposition
      description: |
        Called after call ends (by Genesys event subscription or
        Five9 post-call webhook). Finalizes the unified record.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CompletedNotification'
      responses:
        '200':
          description: Record finalized

  /api/v1/reverse-transfer:
    post:
      summary: Store context for Genesys-to-Five9 reverse transfer
      description: |
        Called when Genesys agent initiates transfer back to Five9
        (e.g., post-call survey). Stores agent context.
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ReverseTransferRequest'
      responses:
        '200':
          description: Reverse context stored

  /api/v1/health:
    get:
      summary: Health check endpoint
      responses:
        '200':
          description: Service healthy

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    PreTransferRequest:
      type: object
      required:
        - correlationId
        - five9CallUUID
        - callerANI
        - calledDNIS
        - intent
        - transferTarget
      properties:
        correlationId:
          type: string
          format: uuid
          description: Unique cross-platform correlation identifier
        five9CallUUID:
          type: string
          description: Five9 internal call session ID
        callerANI:
          type: string
          description: Original caller phone number
        calledDNIS:
          type: string
          description: Original DNIS dialed
        language:
          type: string
          enum: [en, es, fr]
          default: en
        menuChoice:
          type: string
          description: IVR menu option selected (1-9)
        intent:
          type: string
          description: Derived intent/reason code
          enum: [billing, technical_support, sales, operator,
                 self_service_balance, balance_then_agent]
        customerID:
          type: string
          description: Authenticated customer ID
        accountBalance:
          type: string
          description: Account balance (if retrieved)
        transferTarget:
          type: string
          description: Target Genesys Routing Point
          enum: [RP_Billing, RP_TechSupport, RP_Sales, RP_General]
        priority:
          type: string
          enum: [high, normal, low]
          default: normal
        ivrTimestamp:
          type: string
          format: date-time
          description: ISO 8601 timestamp of IVR entry
        ivrDuration:
          type: number
          description: Seconds spent in Five9 IVR

    PreTransferResponse:
      type: object
      properties:
        status:
          type: string
          enum: [stored]
        correlationId:
          type: string
          format: uuid
        storedAt:
          type: string
          format: date-time
        ttl:
          type: number
          description: Seconds until context expires (default 3600)

    CallContext:
      type: object
      properties:
        correlationId:
          type: string
        five9CallUUID:
          type: string
        callerANI:
          type: string
        calledDNIS:
          type: string
        language:
          type: string
        menuChoice:
          type: string
        intent:
          type: string
        customerID:
          type: string
        accountBalance:
          type: string
        transferTarget:
          type: string
        priority:
          type: string
        ivrTimestamp:
          type: string
        ivrDuration:
          type: number
        # Enriched fields (looked up from CRM/backend)
        customerName:
          type: string
        accountType:
          type: string
        customerSegment:
          type: string
          enum: [vip, premium, standard, basic]
        lastInteractionDate:
          type: string
        openCaseCount:
          type: number
        # Status tracking
        status:
          type: string
          enum: [pending_transfer, transferred, routed, completed]
        createdAt:
          type: string
          format: date-time

    RoutedNotification:
      type: object
      properties:
        correlationId:
          type: string
        status:
          type: string
        genesysQueue:
          type: string
        genesysInteractionId:
          type: string
        agentGroup:
          type: string
        routedTimestamp:
          type: string
          format: date-time

    CompletedNotification:
      type: object
      properties:
        correlationId:
          type: string
        platform:
          type: string
          enum: [five9, genesys]
        disposition:
          type: string
        agentId:
          type: string
        handleTime:
          type: number
        wrapUpTime:
          type: number
        completedTimestamp:
          type: string
          format: date-time

    ReverseTransferRequest:
      type: object
      properties:
        correlationId:
          type: string
        genesysInteractionId:
          type: string
        agentId:
          type: string
        disposition:
          type: string
        transferReason:
          type: string
          enum: [post_call_survey, re_ivr, different_department]
        agentNotes:
          type: string
        handleTime:
          type: number
```



### 6.3 Cloud Run Service Implementation (Python)

```python
# main.py - Five9/Genesys Bridge API Service
# Runtime: Python 3.12 on Cloud Run

import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google.cloud import firestore, pubsub_v1, bigquery
from google.auth import default as google_auth_default

# ================================================================
# Configuration
# ================================================================
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "contact-center-bridge")
FIRESTORE_COLLECTION = "bridge_call_contexts"
PUBSUB_TOPIC = "bridge-call-events"
BQ_DATASET = "bridge_analytics"
BQ_TABLE = "call_records"
CONTEXT_TTL_SECONDS = 3600  # 1 hour
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# ================================================================
# Initialize
# ================================================================
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("bridge-api")

app = FastAPI(
    title="Five9-Genesys Bridge API",
    version="1.0.0",
    description="Data bridge and correlation service"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firestore client (context store)
db = firestore.Client(project=PROJECT_ID)

# Pub/Sub client (event streaming)
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC)

# BigQuery client (analytics)
bq_client = bigquery.Client(project=PROJECT_ID)


# ================================================================
# Models
# ================================================================
class PreTransferRequest(BaseModel):
    correlationId: str = Field(..., description="UUID correlation ID")
    five9CallUUID: str = Field(..., description="Five9 call session ID")
    callerANI: str = Field(..., description="Original caller number")
    calledDNIS: str = Field(..., description="Original DNIS")
    language: str = Field(default="en")
    menuChoice: Optional[str] = None
    intent: str = Field(..., description="IVR intent code")
    customerID: Optional[str] = None
    accountBalance: Optional[str] = None
    transferTarget: str = Field(..., description="Genesys RP target")
    priority: str = Field(default="normal")
    ivrTimestamp: Optional[str] = None
    ivrDuration: Optional[float] = None


class PreTransferResponse(BaseModel):
    status: str = "stored"
    correlationId: str
    storedAt: str
    ttl: int = CONTEXT_TTL_SECONDS


class RoutedNotification(BaseModel):
    correlationId: str
    status: str = "routed_to_agent"
    genesysQueue: Optional[str] = None
    genesysInteractionId: Optional[str] = None
    agentGroup: Optional[str] = None
    routedTimestamp: Optional[str] = None


class CompletedNotification(BaseModel):
    correlationId: str
    platform: str  # "five9" or "genesys"
    disposition: Optional[str] = None
    agentId: Optional[str] = None
    handleTime: Optional[float] = None
    wrapUpTime: Optional[float] = None
    completedTimestamp: Optional[str] = None


class ReverseTransferRequest(BaseModel):
    correlationId: str
    genesysInteractionId: Optional[str] = None
    agentId: Optional[str] = None
    disposition: Optional[str] = None
    transferReason: str = "post_call_survey"
    agentNotes: Optional[str] = None
    handleTime: Optional[float] = None


# ================================================================
# Authentication
# ================================================================
async def verify_auth(authorization: str = Header(None)):
    """Verify bearer token (service-to-service auth)."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization")
    
    # In production: validate JWT from Five9/Genesys service accounts
    # For GCP-to-GCP: use Identity-Aware Proxy or service account tokens
    token = authorization.replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return token


# ================================================================
# Helper: Enrich context with CRM data
# ================================================================
async def enrich_customer_context(customer_id: str) -> dict:
    """
    Look up customer in CRM/backend to add context.
    In production: call your CRM API (Salesforce, ServiceNow, etc.)
    """
    if not customer_id:
        return {}
    
    # Example: Firestore customer collection or external CRM API
    try:
        customer_ref = db.collection("customers").document(customer_id)
        customer_doc = customer_ref.get()
        
        if customer_doc.exists:
            data = customer_doc.to_dict()
            return {
                "customerName": data.get("name", ""),
                "accountType": data.get("account_type", "standard"),
                "customerSegment": data.get("segment", "standard"),
                "lastInteractionDate": data.get("last_interaction", ""),
                "openCaseCount": data.get("open_cases", 0),
            }
    except Exception as e:
        logger.warning(f"CRM lookup failed for {customer_id}: {e}")
    
    return {
        "customerName": "",
        "accountType": "unknown",
        "customerSegment": "standard",
        "lastInteractionDate": "",
        "openCaseCount": 0,
    }


# ================================================================
# Helper: Publish event to Pub/Sub
# ================================================================
def publish_event(event_type: str, data: dict):
    """Publish call event for downstream analytics/monitoring."""
    try:
        message = {
            "eventType": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }
        import json
        future = publisher.publish(
            topic_path,
            json.dumps(message).encode("utf-8"),
            event_type=event_type,
            correlation_id=data.get("correlationId", "unknown"),
        )
        future.result(timeout=5)
    except Exception as e:
        logger.error(f"Pub/Sub publish failed: {e}")


# ================================================================
# API Endpoints
# ================================================================

@app.get("/api/v1/health")
async def health_check():
    """Health check for load balancer and monitoring."""
    return {
        "status": "healthy",
        "service": "bridge-api",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@app.post("/api/v1/pre-transfer", response_model=PreTransferResponse)
async def pre_transfer(request: PreTransferRequest, token: str = Depends(verify_auth)):
    """
    Called by Five9 IVR before initiating SIP transfer to Genesys.
    Stores full call context for retrieval by Genesys ORS.
    """
    logger.info(f"Pre-transfer received: correlationId={request.correlationId}, "
                f"intent={request.intent}, target={request.transferTarget}")
    
    # Enrich with CRM data
    enrichment = await enrich_customer_context(request.customerID)
    
    # Build context document
    now = datetime.utcnow()
    context_doc = {
        # Five9 IVR data
        "correlationId": request.correlationId,
        "five9CallUUID": request.five9CallUUID,
        "callerANI": request.callerANI,
        "calledDNIS": request.calledDNIS,
        "language": request.language,
        "menuChoice": request.menuChoice,
        "intent": request.intent,
        "customerID": request.customerID,
        "accountBalance": request.accountBalance,
        "transferTarget": request.transferTarget,
        "priority": request.priority,
        "ivrTimestamp": request.ivrTimestamp,
        "ivrDuration": request.ivrDuration,
        
        # Enriched CRM data
        **enrichment,
        
        # Status tracking
        "status": "pending_transfer",
        "createdAt": now.isoformat(),
        "updatedAt": now.isoformat(),
        "expiresAt": (now + timedelta(seconds=CONTEXT_TTL_SECONDS)).isoformat(),
        
        # Will be populated later
        "genesysInteractionId": None,
        "genesysQueue": None,
        "agentId": None,
        "disposition": None,
        "handleTime": None,
        "completedAt": None,
    }
    
    # Store in Firestore
    doc_ref = db.collection(FIRESTORE_COLLECTION).document(request.correlationId)
    doc_ref.set(context_doc)
    
    # Publish event
    publish_event("PRE_TRANSFER", {
        "correlationId": request.correlationId,
        "callerANI": request.callerANI,
        "intent": request.intent,
        "transferTarget": request.transferTarget,
    })
    
    logger.info(f"Context stored successfully: {request.correlationId}")
    
    return PreTransferResponse(
        status="stored",
        correlationId=request.correlationId,
        storedAt=now.isoformat(),
        ttl=CONTEXT_TTL_SECONDS,
    )


@app.get("/api/v1/context/{correlation_id}")
async def get_context(correlation_id: str, token: str = Depends(verify_auth)):
    """
    Called by Genesys ORS when transferred call arrives.
    Returns full enriched context for routing and screen pop.
    """
    logger.info(f"Context fetch requested: correlationId={correlation_id}")
    
    doc_ref = db.collection(FIRESTORE_COLLECTION).document(correlation_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        logger.warning(f"Context not found: {correlation_id}")
        raise HTTPException(status_code=404, detail="Context not found or expired")
    
    context = doc.to_dict()
    
    # Update status to 'transferred'
    doc_ref.update({
        "status": "transferred",
        "updatedAt": datetime.utcnow().isoformat(),
    })
    
    # Publish event
    publish_event("CONTEXT_FETCHED", {
        "correlationId": correlation_id,
        "fetchedBy": "genesys_ors",
    })
    
    return context


@app.post("/api/v1/routed")
async def call_routed(request: RoutedNotification, token: str = Depends(verify_auth)):
    """
    Called by Genesys ORS after successfully routing to an agent.
    Updates context with Genesys routing details.
    """
    logger.info(f"Call routed: correlationId={request.correlationId}, "
                f"queue={request.genesysQueue}")
    
    doc_ref = db.collection(FIRESTORE_COLLECTION).document(request.correlationId)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Correlation ID not found")
    
    doc_ref.update({
        "status": "routed",
        "genesysQueue": request.genesysQueue,
        "genesysInteractionId": request.genesysInteractionId,
        "agentGroup": request.agentGroup,
        "routedTimestamp": request.routedTimestamp or datetime.utcnow().isoformat(),
        "updatedAt": datetime.utcnow().isoformat(),
    })
    
    # Publish event
    publish_event("CALL_ROUTED", {
        "correlationId": request.correlationId,
        "genesysQueue": request.genesysQueue,
        "agentGroup": request.agentGroup,
    })
    
    return {"status": "updated", "correlationId": request.correlationId}


@app.post("/api/v1/completed")
async def call_completed(request: CompletedNotification, token: str = Depends(verify_auth)):
    """
    Called after call ends. Finalizes the unified record and
    writes to BigQuery for long-term analytics.
    """
    logger.info(f"Call completed: correlationId={request.correlationId}, "
                f"platform={request.platform}")
    
    doc_ref = db.collection(FIRESTORE_COLLECTION).document(request.correlationId)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Correlation ID not found")
    
    now = datetime.utcnow()
    
    # Update Firestore
    doc_ref.update({
        "status": "completed",
        "disposition": request.disposition,
        "agentId": request.agentId,
        "handleTime": request.handleTime,
        "wrapUpTime": request.wrapUpTime,
        "completedAt": request.completedTimestamp or now.isoformat(),
        "updatedAt": now.isoformat(),
    })
    
    # Write final record to BigQuery for analytics
    full_record = doc_ref.get().to_dict()
    _write_to_bigquery(full_record)
    
    # Publish event
    publish_event("CALL_COMPLETED", {
        "correlationId": request.correlationId,
        "platform": request.platform,
        "disposition": request.disposition,
        "handleTime": request.handleTime,
    })
    
    return {"status": "completed", "correlationId": request.correlationId}


@app.post("/api/v1/reverse-transfer")
async def reverse_transfer(request: ReverseTransferRequest, token: str = Depends(verify_auth)):
    """
    Called when Genesys agent transfers call back to Five9.
    Stores agent context so Five9 can continue with awareness.
    """
    logger.info(f"Reverse transfer: correlationId={request.correlationId}, "
                f"reason={request.transferReason}")
    
    doc_ref = db.collection(FIRESTORE_COLLECTION).document(request.correlationId)
    doc = doc_ref.get()
    
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Correlation ID not found")
    
    doc_ref.update({
        "status": "reverse_transfer",
        "reverseTransfer": {
            "reason": request.transferReason,
            "agentId": request.agentId,
            "disposition": request.disposition,
            "agentNotes": request.agentNotes,
            "handleTime": request.handleTime,
            "genesysInteractionId": request.genesysInteractionId,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "updatedAt": datetime.utcnow().isoformat(),
    })
    
    # Publish event
    publish_event("REVERSE_TRANSFER", {
        "correlationId": request.correlationId,
        "reason": request.transferReason,
        "agentId": request.agentId,
    })
    
    return {"status": "reverse_context_stored", "correlationId": request.correlationId}


# ================================================================
# BigQuery Writer
# ================================================================
def _write_to_bigquery(record: dict):
    """Write finalized call record to BigQuery for reporting."""
    try:
        table_ref = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
        
        row = {
            "correlation_id": record.get("correlationId"),
            "five9_call_uuid": record.get("five9CallUUID"),
            "caller_ani": record.get("callerANI"),
            "called_dnis": record.get("calledDNIS"),
            "language": record.get("language"),
            "menu_choice": record.get("menuChoice"),
            "intent": record.get("intent"),
            "customer_id": record.get("customerID"),
            "customer_name": record.get("customerName"),
            "customer_segment": record.get("customerSegment"),
            "transfer_target": record.get("transferTarget"),
            "priority": record.get("priority"),
            "ivr_timestamp": record.get("ivrTimestamp"),
            "ivr_duration_seconds": record.get("ivrDuration"),
            "genesys_queue": record.get("genesysQueue"),
            "genesys_interaction_id": record.get("genesysInteractionId"),
            "agent_id": record.get("agentId"),
            "agent_group": record.get("agentGroup"),
            "disposition": record.get("disposition"),
            "handle_time_seconds": record.get("handleTime"),
            "wrap_up_time_seconds": record.get("wrapUpTime"),
            "status": record.get("status"),
            "created_at": record.get("createdAt"),
            "routed_at": record.get("routedTimestamp"),
            "completed_at": record.get("completedAt"),
        }
        
        errors = bq_client.insert_rows_json(table_ref, [row])
        if errors:
            logger.error(f"BigQuery insert errors: {errors}")
    except Exception as e:
        logger.error(f"BigQuery write failed: {e}")


# ================================================================
# Startup
# ================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
```

### 6.4 Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 6.5 requirements.txt

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
google-cloud-firestore==2.14.0
google-cloud-pubsub==2.19.0
google-cloud-bigquery==3.14.0
pydantic==2.5.3
python-multipart==0.0.6
```

### 6.6 GCP Infrastructure (Terraform snippet)

```hcl
# Cloud Run service
resource "google_cloud_run_v2_service" "bridge_api" {
  name     = "bridge-api"
  location = "us-central1"

  template {
    scaling {
      min_instance_count = 2
      max_instance_count = 20
    }
    
    containers {
      image = "gcr.io/${var.project_id}/bridge-api:latest"
      
      ports {
        container_port = 8080
      }
      
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
      
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
    
    max_instance_request_concurrency = 80
    timeout = "30s"
  }
}

# Firestore (Native mode)
resource "google_firestore_database" "bridge_db" {
  project     = var.project_id
  name        = "(default)"
  location_id = "us-central1"
  type        = "FIRESTORE_NATIVE"
}

# Pub/Sub topic
resource "google_pubsub_topic" "bridge_events" {
  name = "bridge-call-events"
}

# BigQuery dataset
resource "google_bigquery_dataset" "bridge_analytics" {
  dataset_id = "bridge_analytics"
  location   = "US"
}

# BigQuery table
resource "google_bigquery_table" "call_records" {
  dataset_id = google_bigquery_dataset.bridge_analytics.dataset_id
  table_id   = "call_records"
  
  schema = file("schemas/call_records.json")
  
  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }
}

# IAM: Allow Five9 webhook to invoke Cloud Run
resource "google_cloud_run_v2_service_iam_member" "five9_invoker" {
  name   = google_cloud_run_v2_service.bridge_api.name
  role   = "roles/run.invoker"
  member = "serviceAccount:five9-bridge-sa@${var.project_id}.iam.gserviceaccount.com"
}
```

### 6.7 Firestore Document Schema

```
Collection: bridge_call_contexts
Document ID: {correlationId} (UUID)

{
  "correlationId": "550e8400-e29b-41d4-a716-446655440000",
  "five9CallUUID": "five9-sess-abc123",
  "callerANI": "+15551234567",
  "calledDNIS": "18005551234",
  "language": "en",
  "menuChoice": "1",
  "intent": "billing",
  "customerID": "CUST-99001",
  "accountBalance": "$1,234.56",
  "transferTarget": "RP_Billing",
  "priority": "normal",
  "ivrTimestamp": "2024-03-15T10:30:00Z",
  "ivrDuration": 45.2,
  
  "customerName": "John Smith",
  "accountType": "premium",
  "customerSegment": "vip",
  "lastInteractionDate": "2024-03-10",
  "openCaseCount": 2,
  
  "status": "completed",  // pending_transfer → transferred → routed → completed
  "genesysQueue": "RP_Billing",
  "genesysInteractionId": "GNS-INT-456789",
  "agentGroup": "AG_Billing",
  "agentId": "agent.smith",
  "disposition": "resolved",
  "handleTime": 320.5,
  "wrapUpTime": 45.0,
  
  "reverseTransfer": null,  // Populated if transferred back to Five9
  
  "createdAt": "2024-03-15T10:30:45Z",
  "routedTimestamp": "2024-03-15T10:31:02Z",
  "completedAt": "2024-03-15T10:37:22Z",
  "updatedAt": "2024-03-15T10:37:22Z",
  "expiresAt": "2024-03-15T11:30:45Z"
}

Firestore TTL Policy: Auto-delete documents after expiresAt
```



---

## 7. Data Mapping Table (End-to-End)

### 7.1 Five9 → SIP → SBC → Genesys (Forward Direction)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              FORWARD DATA FLOW: Five9 IVR → Genesys Agent                                    │
├────────────────────┬─────────────────────────┬───────────────────────────┬─────────────────────────┬─────────┤
│ Five9 CAV /        │ Five9 Outbound          │ SBC HMR Output            │ Genesys UserData        │ Agent   │
│ IVR Variable       │ SIP X-Header            │ (to Genesys)              │ Key                     │ Desktop │
├────────────────────┼─────────────────────────┼───────────────────────────┼─────────────────────────┼─────────┤
│ {CorrelationId}    │ X-Five9-CorrelationId   │ X-Bridge-CorrelationId    │ Bridge_CorrelationId    │ Yes     │
│ {Five9CallUUID}    │ X-Five9-CallUUID        │ X-Bridge-CallUUID         │ Bridge_Five9CallUUID    │ Yes     │
│ {CallerANI}        │ X-Five9-ANI             │ P-Asserted-Identity       │ ANI (native)            │ Yes     │
│ {CalledDNIS}       │ X-Five9-DNIS            │ X-Bridge-DNIS             │ Bridge_DNIS             │ Yes     │
│ {Language}         │ X-Five9-Language         │ X-Bridge-Language         │ Bridge_Language          │ Yes     │
│ {MenuChoice}       │ X-Five9-MenuChoice       │ X-Bridge-MenuChoice       │ Bridge_MenuChoice        │ Yes     │
│ {Intent}           │ X-Five9-Intent           │ X-Bridge-Intent           │ Bridge_Intent            │ Yes     │
│ {CustomerID}       │ X-Five9-CustID           │ X-Bridge-CustID           │ Bridge_CustomerID        │ Yes     │
│ {AccountBalance}   │ X-Five9-Balance          │ X-Bridge-Balance          │ Bridge_AccountBalance    │ Yes     │
│ {Priority}         │ X-Five9-Priority         │ X-Bridge-Priority         │ Bridge_Priority          │ Yes     │
│ {TransferTarget}   │ X-Five9-TransferTarget   │ X-Bridge-TransferTarget   │ Bridge_TransferTarget    │ No      │
│ {IVRTimestamp}     │ X-Five9-Timestamp        │ X-Bridge-Timestamp        │ Bridge_IVRTimestamp      │ Yes     │
│ (system.callDur)   │ (in webhook only)        │ (from middleware)         │ Bridge_IVRDuration       │ Yes     │
│ —                  │ —                        │ —                         │ Bridge_CustomerName *    │ Yes     │
│ —                  │ —                        │ —                         │ Bridge_CustomerSegment * │ Yes     │
│ —                  │ —                        │ —                         │ Bridge_OpenCases *       │ Yes     │
│ —                  │ —                        │ —                         │ Bridge_Source            │ Yes     │
├────────────────────┴─────────────────────────┴───────────────────────────┴─────────────────────────┴─────────┤
│ * = Enriched by GCP middleware (not in SIP headers, fetched via ORS External Service call)                    │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Genesys → SIP → SBC → Five9 (Reverse Direction)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              REVERSE DATA FLOW: Genesys Agent → Five9                                        │
├─────────────────────────┬────────────────────────────┬──────────────────────────┬────────────────────────────┤
│ Genesys UserData Key    │ Genesys Outbound           │ SBC HMR Output           │ Five9 Inbound              │
│                         │ SIP X-Header               │ (to Five9)               │ CAV / XSIP Variable       │
├─────────────────────────┼────────────────────────────┼──────────────────────────┼────────────────────────────┤
│ Bridge_CorrelationId    │ X-Genesys-CorrelationId    │ X-Five9-CorrelationId    │ {xsip_correlationid}       │
│ Bridge_CustomerID       │ X-Genesys-CustomerID       │ X-Five9-CustID           │ {xsip_custid}              │
│ Bridge_Intent           │ X-Genesys-Intent           │ X-Five9-Intent           │ {xsip_intent}              │
│ Genesys_Disposition     │ X-Genesys-Disposition      │ X-Five9-Disposition      │ {xsip_disposition}         │
│ Genesys_AgentID         │ X-Genesys-AgentID          │ X-Five9-AgentID          │ {xsip_agentid}             │
│ Genesys_HandleTime      │ X-Genesys-HandleTime       │ X-Five9-HandleTime       │ {xsip_handletime}          │
└─────────────────────────┴────────────────────────────┴──────────────────────────┴────────────────────────────┘
```

### 7.3 Unified Correlation ID Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        CORRELATION ID: 550e8400-e29b-41d4-a716-446655440000              │
├──────────────┬──────────────────────────────────────────────────────────────────────────┤
│ Platform     │ Where the Correlation ID appears                                         │
├──────────────┼──────────────────────────────────────────────────────────────────────────┤
│ Five9        │ • CAV: Bridge_Context.CorrelationId                                      │
│              │ • Five9 Call Log (custom field)                                           │
│              │ • Five9 Reporting API: getCallData() → CAV value                         │
│              │ • Five9 Recording metadata                                               │
├──────────────┼──────────────────────────────────────────────────────────────────────────┤
│ SBC          │ • CDR (Call Detail Record): X-Bridge-CorrelationId logged                │
│              │ • SIP trace logs (INVITE headers)                                        │
├──────────────┼──────────────────────────────────────────────────────────────────────────┤
│ GCP          │ • Firestore document ID                                                  │
│ Middleware   │ • Pub/Sub message attribute: correlation_id                              │
│              │ • BigQuery: call_records.correlation_id                                  │
│              │ • Cloud Logging: structured log field                                    │
├──────────────┼──────────────────────────────────────────────────────────────────────────┤
│ Genesys      │ • UserData key: Bridge_CorrelationId                                    │
│              │ • Info Mart: INTERACTION_FACT.USER_DATA_1 (mapped)                       │
│              │ • Pulse dashboard: custom filter                                        │
│              │ • Genesys Recording metadata (attached data)                            │
├──────────────┼──────────────────────────────────────────────────────────────────────────┤
│ BigQuery     │ • Unified JOIN key across all data sources                              │
│ (Reporting)  │ • Query: SELECT * FROM call_records WHERE correlation_id = 'uuid-xxx'   │
└──────────────┴──────────────────────────────────────────────────────────────────────────┘
```



---

## 8. Failover and Error Handling

### 8.1 Failure Scenarios Matrix

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ FAILURE SCENARIO              │ DETECTION              │ HANDLING                    │ CALLER IMPACT    │
├───────────────────────────────┼────────────────────────┼─────────────────────────────┼──────────────────┤
│ Genesys SIP Server down       │ SBC OPTIONS ping fails │ SBC returns 503 to Five9    │ Stays in Five9   │
│ (both primary + backup)       │ (15s interval)         │ Five9 IVR: offer callback   │ queue or callback│
├───────────────────────────────┼────────────────────────┼─────────────────────────────┼──────────────────┤
│ Genesys ORS timeout           │ SIP 408 or 504 from    │ SBC alt-route to backup     │ Delayed 10s,     │
│ (strategy hung)               │ Genesys after 10s      │ If both fail: 503 to Five9  │ then queued      │
├───────────────────────────────┼────────────────────────┼─────────────────────────────┼──────────────────┤
│ Genesys all agents busy       │ ORS route.failed event │ ORS: overflow to AG_General │ Longer wait      │
│ (no available agents)         │ after VQ timeout       │ If still fails: 503         │ or callback      │
├───────────────────────────────┼────────────────────────┼─────────────────────────────┼──────────────────┤
│ SBC failure (one of pair)     │ HA heartbeat miss      │ Standby SBC takes over      │ ~1-2s blip       │
│                               │ (500ms detection)      │ (VIP failover)              │ (mid-call)       │
├───────────────────────────────┼────────────────────────┼─────────────────────────────┼──────────────────┤
│ GCP middleware down           │ ORS HTTP timeout (5s)  │ ORS: proceed with SIP       │ No enriched data │
│ (Cloud Run)                   │                        │ headers only (graceful      │ but call routes  │
│                               │                        │ degradation)                │ normally         │
├───────────────────────────────┼────────────────────────┼─────────────────────────────┼──────────────────┤
│ Five9 pre-transfer webhook    │ HTTP error/timeout     │ Five9 IVR: proceed with     │ None (transfer   │
│ to middleware fails           │ from Cloud Run         │ transfer anyway (best       │ still works)     │
│                               │                        │ effort context)             │                  │
├───────────────────────────────┼────────────────────────┼─────────────────────────────┼──────────────────┤
│ Network: SBC ↔ Five9 down     │ Five9 SIP timeout      │ Five9: "Sorry" message      │ Call drops or    │
│ (internet/TLS failure)        │ (no 100 Trying)        │ + offer callback            │ callback offered │
├───────────────────────────────┼────────────────────────┼─────────────────────────────┼──────────────────┤
│ Network: SBC ↔ Genesys down   │ SBC OPTIONS ping fails │ SBC marks Genesys OOS       │ 503 → Five9      │
│ (internal network issue)      │                        │ Returns 503 to Five9        │ handles failover │
├───────────────────────────────┼────────────────────────┼─────────────────────────────┼──────────────────┤
│ SIP header corruption         │ Genesys: empty/null    │ ORS: DefaultRouting path    │ Routes to general│
│ (headers missing)             │ UserData values        │ (no Bridge data)            │ queue, no pop    │
├───────────────────────────────┼────────────────────────┼─────────────────────────────┼──────────────────┤
│ Five9 platform outage         │ No calls arriving      │ Carrier reroutes DIDs       │ Calls go direct  │
│ (complete Five9 failure)      │ at SBC from Five9      │ directly to Genesys (bypass)│ to Genesys       │
└───────────────────────────────┴────────────────────────┴─────────────────────────────┴──────────────────┘
```

### 8.2 Five9 IVR Failover Script (TRANSFER_FAILED Module)

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRANSFER_FAILED Module (Five9 IVR)                                  │
│                                                                     │
│  Trigger: SIP 503/408/500 response from SBC (Genesys unavailable)   │
│                                                                     │
│  1. [Play Message]                                                   │
│     "We're experiencing higher than normal call volumes.            │
│      Your call is important to us."                                  │
│                                                                     │
│  2. [DTMF Menu]                                                     │
│     "Press 1 to receive a callback when an agent is available"      │
│     "Press 2 to continue waiting"                                    │
│     "Press 3 to leave a voicemail"                                  │
│                                                                     │
│  3. [CASE]                                                           │
│     Option 1 → CALLBACK_MODULE:                                      │
│       • Collect callback number (or confirm ANI)                     │
│       • HTTP POST to middleware: /api/v1/callback-request            │
│         {correlationId, ani, intent, preferredTime}                  │
│       • "We'll call you back within 30 minutes. Goodbye."           │
│       • END CALL                                                     │
│                                                                     │
│     Option 2 → RETRY_TRANSFER:                                       │
│       • Wait 30 seconds (play MOH)                                   │
│       • Retry SIP transfer to SBC                                    │
│       • If still fails after 3 retries → force to Option 1          │
│                                                                     │
│     Option 3 → VOICEMAIL_MODULE:                                     │
│       • "Please leave a message after the tone"                      │
│       • Record voicemail                                             │
│       • HTTP POST to middleware: /api/v1/voicemail                   │
│         {correlationId, recordingUrl}                                │
│       • END CALL                                                     │
│                                                                     │
│  Retry Logic:                                                        │
│    max_retries = 3                                                   │
│    retry_interval = 30s                                              │
│    backoff = linear (30s, 60s, 90s)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.3 SBC Failover Configuration (Oracle)

```
; ================================================================
; SBC FAILOVER: Five9 → Genesys with automatic retry
; ================================================================

; Session Agent Group with failover behavior
session-agent-group
    group-name               SAG-Genesys
    strategy                 RoundRobin
    dest
        hostname             genesys-sip-primary
        priority             1
    dest
        hostname             genesys-sip-backup
        priority             2
    ; If both fail, return 503 to originator (Five9)
    
; SIP response code handling
session-agent
    hostname                 genesys-sip-primary
    ; Mark out-of-service on these responses
    stop-recurse             401,403,404,503
    ; Retry on these (to backup)
    retry-after-value        3
    out-service-503          enabled
    ; Response timeout
    response-timeout         10

; Local policy with cost-based failover
local-policy
    from-address             *
    to-address               sip:RP_*@*
    source-realm             five9
    policy-attribute
        next-hop             SAG-Genesys
        realm                genesys
        cost                 1
    ; If Genesys completely unreachable, respond 503
    ; Five9 IVR handles the failover to caller
```

### 8.4 Genesys ORS Failover Logic

```xml
<!-- In Bridge_Master_Router strategy -->

<!-- TIMEOUT HANDLING: If external service (middleware) is slow -->
<state id="FetchFullContext">
  <onentry>
    <send event="http.request" target="ExternalService">
      <param name="timeout" value="5000"/>  <!-- 5 second hard timeout -->
    </send>
  </onentry>
  
  <!-- Success path -->
  <transition event="http.response.200" target="EnrichUserData"/>
  
  <!-- ANY failure: gracefully degrade, route with SIP headers only -->
  <transition event="http.response.4*" target="RouteByHeaders">
    <log level="warn" expr="'Middleware 4xx. Using SIP headers only.'"/>
  </transition>
  <transition event="http.response.5*" target="RouteByHeaders">
    <log level="error" expr="'Middleware 5xx. Using SIP headers only.'"/>
  </transition>
  <transition event="error.timeout" target="RouteByHeaders">
    <log level="error" expr="'Middleware timeout. Using SIP headers only.'"/>
  </transition>
  <transition event="error.*" target="RouteByHeaders">
    <log level="error" expr="'Middleware error. Using SIP headers only.'"/>
  </transition>
</state>

<!-- ROUTING FAILURE: Escalation chain -->
<state id="RouteToBilling">
  <onentry>
    <send event="route.request">
      <param name="target" value="AG_Billing"/>
      <param name="timeout" value="60"/>
    </send>
  </onentry>
  <transition event="route.done" target="PostRouteUpdate"/>
  <transition event="route.failed" target="OverflowLevel1"/>
</state>

<state id="OverflowLevel1">
  <onentry>
    <!-- Try general pool -->
    <send event="route.request">
      <param name="target" value="AG_General"/>
      <param name="priority" value="9"/>
      <param name="timeout" value="60"/>
    </send>
  </onentry>
  <transition event="route.done" target="PostRouteUpdate"/>
  <transition event="route.failed" target="OverflowLevel2"/>
</state>

<state id="OverflowLevel2">
  <onentry>
    <!-- Last resort: any agent with any skill -->
    <send event="route.request">
      <param name="target_type" value="any_agent"/>
      <param name="priority" value="10"/>
      <param name="timeout" value="120"/>
    </send>
  </onentry>
  <transition event="route.done" target="PostRouteUpdate"/>
  <transition event="route.failed" target="GenesysUnavailable"/>
</state>

<state id="GenesysUnavailable">
  <onentry>
    <!-- Return 503 - Five9 IVR handles caller experience -->
    <send event="route.reject">
      <param name="reason" value="503"/>
    </send>
  </onentry>
  <transition target="Exit"/>
</state>
```

### 8.5 Carrier-Level Failover (Bypass Five9 Entirely)

If Five9 has a complete platform outage, configure the PSTN carrier to reroute:

```
┌─────────────────────────────────────────────────────────────────────┐
│ CARRIER FAILOVER PLAN (coordinate with carrier)                      │
│                                                                     │
│ Normal:    DNIS → Carrier → SBC → Five9 → SBC → Genesys            │
│                                                                     │
│ Five9 Down: DNIS → Carrier → SBC → Genesys (direct)                │
│                                                                     │
│ Implementation options:                                              │
│   A) Carrier-level failover:                                         │
│      • Carrier monitors Five9 endpoint health                        │
│      • Auto-redirects to backup trunk (SBC → Genesys direct)        │
│                                                                     │
│   B) SBC-level failover:                                             │
│      • SBC detects Five9 OOS (OPTIONS ping failure)                  │
│      • SBC local policy: if Five9 unreachable, route PSTN→Genesys   │
│                                                                     │
│ SBC Config (Option B):                                               │
│                                                                     │
│ local-policy                                                         │
│     from-address             *                                       │
│     to-address               *                                       │
│     source-realm             pstn                                    │
│     policy-attribute                                                 │
│         next-hop             SAG-Five9          ; Primary             │
│         cost                 1                                       │
│     policy-attribute                                                 │
│         next-hop             SAG-Genesys        ; Failover            │
│         cost                 10                                       │
│                                                                     │
│ Note: When routing directly to Genesys (bypass Five9),              │
│       no IVR data will be available. Genesys default strategy       │
│       handles the call with basic DNIS-based routing.                │
└─────────────────────────────────────────────────────────────────────┘
```



---

## 9. Monitoring and Unified Correlation Tracking

### 9.1 Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          MONITORING & OBSERVABILITY STACK                             │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                     GCP CLOUD MONITORING DASHBOARD                           │   │
│  │                                                                             │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │   │
│  │  │ Five9 Health │  │  SBC Health  │  │ Genesys      │  │ Middleware    │  │   │
│  │  │ • API avail  │  │ • SIP ping   │  │ • SIP Server │  │ • Latency     │  │   │
│  │  │ • Call volume│  │ • Sessions   │  │ • ORS health │  │ • Error rate  │  │   │
│  │  │ • IVR errors │  │ • HMR errors │  │ • Agent login│  │ • Throughput  │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └───────────────┘  │   │
│  │                                                                             │   │
│  │  ┌──────────────────────────────────────────────────────────────────────┐  │   │
│  │  │                    REAL-TIME ALERT RULES                              │  │   │
│  │  │  • Transfer failure rate > 5% in 5 min → PagerDuty P1               │  │   │
│  │  │  • Middleware latency p99 > 3s → Slack warning                       │  │   │
│  │  │  • SBC session count > 180/200 → capacity alert                     │  │   │
│  │  │  • Genesys OOS (OPTIONS fail) → PagerDuty P1                        │  │   │
│  │  │  • Correlation ID miss rate > 10% → investigate                     │  │   │
│  │  └──────────────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  Data Sources:                                                                      │
│    • Five9 Statistics API (polled every 60s)                                        │
│    • Oracle SBC SNMP + CDR logs                                                     │
│    • Genesys Stat Server (real-time metrics)                                        │
│    • GCP Cloud Run metrics (built-in)                                               │
│    • Pub/Sub message flow metrics                                                   │
│    • Firestore read/write latency                                                   │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Key Performance Indicators (KPIs)

| KPI | Target | Source | Alert Threshold |
|---|---|---|---|
| **Transfer Success Rate** | > 99% | SBC CDR (INVITE → 200 OK) | < 95% = P1 alert |
| **Transfer Latency** (Five9→Agent answer) | < 15s | Middleware timestamps | > 30s = warning |
| **Middleware API Latency** (p95) | < 500ms | Cloud Run metrics | > 2s = warning |
| **Middleware API Availability** | 99.9% | Cloud Run uptime | < 99.5% = P1 |
| **Correlation Match Rate** | > 98% | Compare middleware store vs Genesys fetch | < 90% = P2 |
| **SBC Concurrent Sessions** | < 80% capacity | SNMP polling | > 90% = warning |
| **Genesys Agent Availability** | > 90% agents ready | Stat Server | < 50% = alert |
| **Five9 IVR Completion Rate** | > 95% | Five9 Reporting API | < 90% = investigate |
| **Failed Transfer → Callback** | Track volume | Middleware logs | Spike = capacity issue |
| **End-to-End Call Duration** | Varies by intent | BigQuery analytics | Anomaly detection |

### 9.3 Structured Logging (Cloud Logging)

All components log with the correlation ID for cross-platform tracing:

```json
// Five9 IVR (logged to Five9 + sent to middleware)
{
  "timestamp": "2024-03-15T10:30:45.123Z",
  "severity": "INFO",
  "component": "five9_ivr",
  "correlationId": "550e8400-e29b-41d4-a716-446655440000",
  "event": "menu_selection",
  "data": {
    "ani": "+15551234567",
    "dnis": "18005551234",
    "menuChoice": "1",
    "intent": "billing"
  }
}

// GCP Middleware (Cloud Logging - structured)
{
  "timestamp": "2024-03-15T10:30:46.456Z",
  "severity": "INFO",
  "component": "bridge_api",
  "correlationId": "550e8400-e29b-41d4-a716-446655440000",
  "event": "pre_transfer_stored",
  "latencyMs": 45,
  "data": {
    "intent": "billing",
    "transferTarget": "RP_Billing",
    "customerSegment": "vip"
  }
}

// SBC CDR (Oracle SBC RADIUS/local CDR)
{
  "timestamp": "2024-03-15T10:30:47.789Z",
  "component": "oracle_sbc",
  "correlationId": "550e8400-e29b-41d4-a716-446655440000",
  "event": "sip_invite_forwarded",
  "data": {
    "source": "five9-primary",
    "destination": "genesys-sip-primary",
    "sipCallId": "five9-call-abc123@five9.com",
    "responseCode": 200,
    "setupTimeMs": 1200
  }
}

// Genesys ORS (logged to Genesys Log DB + forwarded to Cloud Logging)
{
  "timestamp": "2024-03-15T10:30:48.012Z",
  "severity": "INFO",
  "component": "genesys_ors",
  "correlationId": "550e8400-e29b-41d4-a716-446655440000",
  "event": "route_decision",
  "data": {
    "intent": "billing",
    "targetQueue": "AG_Billing",
    "priority": 5,
    "ewt": 45,
    "agentSelected": "agent.smith@company.com"
  }
}
```

### 9.4 Cloud Monitoring Dashboard (Metrics)

```yaml
# dashboard.yaml - GCP Monitoring Dashboard definition

displayName: "Five9-Genesys Bridge Health"

widgets:
  - title: "Transfer Success Rate (5-min rolling)"
    scorecard:
      timeSeriesQuery:
        prometheusQuery: |
          sum(rate(bridge_transfers_total{status="success"}[5m])) /
          sum(rate(bridge_transfers_total[5m])) * 100
      thresholds:
        - value: 99
          color: GREEN
        - value: 95
          color: YELLOW
        - value: 90
          color: RED

  - title: "Middleware API Latency (p95)"
    xyChart:
      timeSeries:
        - filter: 'resource.type="cloud_run_revision" AND
                   metric.type="run.googleapis.com/request_latencies"'
          perSeriesAligner: ALIGN_PERCENTILE_95

  - title: "Active SBC Sessions"
    xyChart:
      timeSeries:
        - filter: 'metric.type="custom.googleapis.com/sbc/active_sessions"'
      thresholds:
        - value: 180
          color: RED

  - title: "Genesys Agent Availability"
    xyChart:
      timeSeries:
        - filter: 'metric.type="custom.googleapis.com/genesys/agents_ready"'

  - title: "Call Volume by Intent"
    xyChart:
      timeSeries:
        - filter: 'metric.type="custom.googleapis.com/bridge/calls_by_intent"'
          groupBy: ["intent"]

  - title: "Failed Transfers → Callback Requests"
    xyChart:
      timeSeries:
        - filter: 'metric.type="custom.googleapis.com/bridge/callbacks_requested"'
```

### 9.5 Alert Policies

```yaml
# alerts.yaml - GCP Monitoring Alert Policies

# ALERT 1: Transfer Failure Rate
- displayName: "Bridge Transfer Failure Rate > 5%"
  conditions:
    - conditionThreshold:
        filter: 'metric.type="custom.googleapis.com/bridge/transfer_failure_rate"'
        comparison: COMPARISON_GT
        thresholdValue: 5.0
        duration: "300s"  # 5 minutes sustained
  notificationChannels: [pagerduty-p1, slack-oncall]
  documentation:
    content: |
      Transfer failure rate exceeded 5%. Check:
      1. SBC health (are Genesys agents pingable?)
      2. Genesys SIP Server status
      3. Network connectivity SBC ↔ Genesys

# ALERT 2: Middleware Latency
- displayName: "Bridge API Latency p99 > 3s"
  conditions:
    - conditionThreshold:
        filter: 'resource.type="cloud_run_revision" AND
                 metric.type="run.googleapis.com/request_latencies"'
        aggregations:
          - alignmentPeriod: "60s"
            perSeriesAligner: ALIGN_PERCENTILE_99
        comparison: COMPARISON_GT
        thresholdValue: 3000  # 3000ms
        duration: "300s"
  notificationChannels: [slack-engineering]

# ALERT 3: Genesys SIP Server Down
- displayName: "Genesys SIP Server Unreachable"
  conditions:
    - conditionAbsent:
        filter: 'metric.type="custom.googleapis.com/sbc/genesys_options_response"'
        duration: "60s"  # No response for 60s
  notificationChannels: [pagerduty-p1, slack-oncall, email-management]

# ALERT 4: SBC Capacity Warning
- displayName: "SBC Session Capacity > 90%"
  conditions:
    - conditionThreshold:
        filter: 'metric.type="custom.googleapis.com/sbc/session_utilization"'
        comparison: COMPARISON_GT
        thresholdValue: 90
        duration: "120s"
  notificationChannels: [slack-capacity, email-engineering]

# ALERT 5: Correlation ID Mismatch
- displayName: "Correlation Match Rate Below 90%"
  conditions:
    - conditionThreshold:
        filter: 'metric.type="custom.googleapis.com/bridge/correlation_miss_rate"'
        comparison: COMPARISON_GT
        thresholdValue: 10  # 10% miss rate
        duration: "600s"
  notificationChannels: [slack-engineering]
```

### 9.6 BigQuery Unified Reporting Query

```sql
-- Unified cross-platform call report
-- Joins Five9 IVR data with Genesys agent data via correlation_id

SELECT
  cr.correlation_id,
  cr.caller_ani,
  cr.called_dnis,
  cr.language,
  cr.intent,
  cr.customer_id,
  cr.customer_name,
  cr.customer_segment,
  cr.priority,
  
  -- Five9 IVR metrics
  cr.ivr_duration_seconds AS five9_ivr_duration,
  cr.menu_choice AS ivr_menu_selection,
  cr.ivr_timestamp AS ivr_entry_time,
  
  -- Transfer metrics
  TIMESTAMP_DIFF(
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', cr.routed_at),
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', cr.ivr_timestamp),
    SECOND
  ) AS total_transfer_time_seconds,
  
  -- Genesys agent metrics
  cr.genesys_queue,
  cr.agent_group,
  cr.agent_id,
  cr.disposition,
  cr.handle_time_seconds,
  cr.wrap_up_time_seconds,
  
  -- Total customer journey time
  TIMESTAMP_DIFF(
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', cr.completed_at),
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', cr.ivr_timestamp),
    SECOND
  ) AS total_journey_time_seconds,
  
  cr.status,
  cr.created_at,
  cr.completed_at

FROM `contact-center-bridge.bridge_analytics.call_records` cr
WHERE DATE(cr.created_at) = CURRENT_DATE()
ORDER BY cr.created_at DESC
LIMIT 1000;


-- Daily summary dashboard query
SELECT
  DATE(created_at) AS call_date,
  intent,
  COUNT(*) AS total_calls,
  COUNTIF(status = 'completed') AS completed_calls,
  COUNTIF(status = 'pending_transfer') AS failed_transfers,
  AVG(ivr_duration_seconds) AS avg_ivr_duration,
  AVG(handle_time_seconds) AS avg_handle_time,
  AVG(TIMESTAMP_DIFF(
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', completed_at),
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', ivr_timestamp),
    SECOND
  )) AS avg_total_journey_time,
  COUNTIF(priority = 'high') AS high_priority_calls

FROM `contact-center-bridge.bridge_analytics.call_records`
WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY call_date, intent
ORDER BY call_date DESC, total_calls DESC;
```

### 9.7 SBC CDR Export to GCP

Configure the Oracle SBC to export CDRs to GCP for centralized monitoring:

```
; Oracle SBC: CDR configuration (RADIUS or local CSV)
ORACLE-SBC(configure)# session-router
ORACLE-SBC(session-router)# account-config

account-config
    state                    enabled
    hostname                 sbc-primary
    port                     1813
    strategy                 hunt
    
    ; RADIUS server (forward CDRs to GCP collector)
    account-servers
        hostname             gcp-radius-collector.internal
        port                 1813
        secret               <shared_secret>
        state                enabled
    
    ; CDR fields to include
    vsa-id-range             1-100
    cdr-output-inclusive     enabled
    
    ; Include custom headers in CDR
    generate-cdr             stop-record
    intermediate-period      0
    
    ; Fields: correlationId, source, destination, duration, response code
```

---

## 10. Deployment Checklist

### Phase 1: Infrastructure Setup
- [ ] Deploy Oracle SBC pair (HA) with network interfaces configured
- [ ] Configure TLS certificates (Five9 CA trust, SBC server cert)
- [ ] Deploy GCP Cloud Run middleware service
- [ ] Create Firestore database and collections
- [ ] Set up Pub/Sub topic and BigQuery dataset
- [ ] Configure VPN/Interconnect between SBC and GCP (if applicable)
- [ ] Verify network connectivity: SBC ↔ Five9, SBC ↔ Genesys, SBC ↔ GCP

### Phase 2: Platform Configuration
- [ ] Configure Five9 SIP trunk (Genesys_Bridge_Trunk)
- [ ] Create Five9 inbound campaign and IVR script
- [ ] Define Five9 Call Variables (CAV group)
- [ ] Configure Genesys Trunk DN, Routing Points, Virtual Queues
- [ ] Update SIP Server options (header mapping)
- [ ] Deploy ORS/Composer routing strategy
- [ ] Configure agent desktop screen pop layout

### Phase 3: Testing
- [ ] SIP connectivity test (OPTIONS ping): SBC ↔ Five9
- [ ] SIP connectivity test (OPTIONS ping): SBC ↔ Genesys
- [ ] End-to-end test call: PSTN → Five9 IVR → menu → transfer → Genesys agent
- [ ] Verify SIP headers pass through correctly (SIP trace at each hop)
- [ ] Verify middleware stores and returns context correctly
- [ ] Verify agent screen pop displays all Five9 IVR context
- [ ] Test failover: disable Genesys primary → verify backup takes over
- [ ] Test failover: disable both Genesys → verify Five9 callback flow
- [ ] Test failover: kill middleware → verify graceful degradation
- [ ] Load test: simulate 50 concurrent transfers
- [ ] Verify BigQuery records and correlation ID consistency
- [ ] Test reverse transfer: Genesys → Five9 (post-call survey)

### Phase 4: Go-Live
- [ ] Enable monitoring dashboards and alerts
- [ ] Configure PagerDuty/Slack notification channels
- [ ] Brief NOC/support teams on new architecture
- [ ] Start with 10% traffic (pilot DNIS), monitor for 48 hours
- [ ] Gradually increase to 50%, then 100%
- [ ] Confirm unified reporting in BigQuery

---

## Sources & References

- [Oracle SBC Routing Configuration](https://docs.oracle.com/en/industries/communications/session-border-controller/9.3.0/configuration/configuring-routing.html)
- [Oracle SBC HMR Configuration](https://docs.oracle.com/en/industries/communications/session-border-controller/10.0.0/hmr/hmr-configuration.html)
- [Oracle SBC Session Agents](https://docs.oracle.com/en/industries/communications/session-border-controller/9.3.0/configuration/sip-session-agents.html)
- [Genesys Composer ForceRoute Block](https://docs.genesys.com/Documentation/Composer/latest/Help/ForceRouteBlock)
- [Genesys Composer UserData Block](https://docs.genesys.com/Documentation/Composer/latest/Help/UserDataBlock)
- [Genesys ORS Architecture](https://docs.genesys.com/Documentation/OS/latest/Deployment/Arch)
- [Genesys SIP Cluster Routing Principles](https://docs.genesys.com/Documentation/SIPC/latest/Solution/RoutingPrinciples)
- [Five9 Studio SIP Header Node](https://docs.studioportal.io/Content/studio-nodes/topics/sip-header.htm)
- [Five9 XSIP Variables](https://docs.studioportal.io/Content/studio-build/content-types/variables-xsip.htm)
- [Five9 Network Requirements](https://www.five9.com/trust/network)
- [GCP Cloud Run Documentation](https://cloud.google.com/run/docs)
- [GCP Cloud Monitoring](https://cloud.google.com/monitoring/docs)

*Content was rephrased for compliance with licensing restrictions.*
