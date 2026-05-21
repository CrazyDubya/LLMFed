# Roster, Staff, Audience, and Demographics

Design for roster, contracts, wrestler stats/personalities, staff types, and audience demographics.

---

## 1. Roster

The **Roster** is a federation's active talent list: wrestlers and staff under contract.

| Field | Description |
|-------|-------------|
| `federation_id` | Owning federation |
| `wrestler_ids` | Participant agent IDs |
| `staff_ids` | Announcers, refs, managers, valets |
| `contracts` | Active contracts |

---

## 2. Contracts

A **Contract** links an agent to a federation with terms.

| Field | Description |
|-------|-------------|
| `agent_id` | Wrestler or staff agent |
| `federation_id` | Federation |
| `contract_type` | full_time, part_time, ppv_appearance, developmental, legend |
| `status` | active, expired, terminated, suspended |
| `start_date`, `end_date` | Contract period |
| `salary_terms` | Optional salary/clause terms |

---

## 3. Wrestler Stats

**WrestlerStats** (per participant per federation):

| Field | Description |
|-------|-------------|
| `wins`, `losses`, `draws`, `no_contests` | Match record |
| `title_reigns` | Number of championship reigns |
| `total_matches`, `main_events`, `ppv_matches` | Activity |

Derived: `win_rate = wins / total_matches`.

---

## 4. Wrestler Personality (Dual Life)

**WrestlerPersonality** supports POV filtering:

- **Gimmick traits**: What TV and crowd see (character: brave, ruthless, mysterious).
- **Personal traits**: What backstage and promoter see (real: confidence, ego, loyalty).

| Field | Description |
|-------|-------------|
| `gimmick_traits` | Dict[str, int] 0–100 |
| `personal_traits` | Dict[str, int] 0–100 |
| `backstage_notes` | Promoter/backstage notes |

---

## 5. Staff Types

### Announcers

| Field | Description |
|-------|-------------|
| `announcer_type` | play_by_play, color, special |
| `signature_phrases` | Catchphrases |
| `bias_toward` | Favorite wrestler ID |
| `voice_style` | excited, calm |

### Referees

| Field | Description |
|-------|-------------|
| `strictness` | 1–10 (lenient–strict) |
| `specialty_matches` | hardcore, cage, etc. |

### Managers

| Field | Description |
|-------|-------------|
| `client_ids` | Wrestler(s) managed |
| `alignment` | babyface, heel, tweener |
| `mic_skill` | 1–10 |

### Valets

| Field | Description |
|-------|-------------|
| `client_ids` | Wrestler(s) accompanied |
| `interference_tendency` | 1–10 (never–often) |

---

## 6. Audience & Demographics

### Fan Types

| Type | Description |
|------|-------------|
| **superfan** | Hardcore, knows history, intense reactions |
| **super_viewer** | Watches every show, high engagement |
| **common_viewer** | Regular viewer, moderate engagement |
| **common_fan** | Casual fan, lower engagement |

### Demographics

- **Age**: kids, teens, young_adult, adult, mature, senior
- **Region**: local, regional, national, international
- **Fan type distribution**: % per fan type

### Audience Segment

Per-card mix of fan types for crowd simulation:

- `superfan_pct`, `super_viewer_pct`, `common_viewer_pct`, `common_fan_pct`
- Used to weight crowd reactions by engagement level

---

## 7. DB Tables

| Table | Purpose |
|-------|---------|
| `contracts` | Agent–federation contracts |
| `wrestler_stats` | Per-agent per-federation stats |
| `wrestler_personalities` | Gimmick vs personal traits |
| `staff_profiles` | Announcer/ref/manager/valet profiles |
| `audience_demographics` | Federation demographics |
| `audience_segments` | Per-card fan mix |

---

## 8. Implementation Status

| Concept | Pydantic | DB | Notes |
|---------|----------|-----|------|
| Roster | ✅ | Via contracts | Roster = federation agents + contracts |
| Contract | ✅ | ✅ | ContractDB |
| WrestlerStats | ✅ | ✅ | WrestlerStatsDB |
| WrestlerPersonality | ✅ | ✅ | WrestlerPersonalityDB |
| AnnouncerProfile | ✅ | Via staff_profiles | staff_type=announcer |
| RefereeProfile | ✅ | Via staff_profiles | staff_type=referee |
| ManagerProfile | ✅ | Via staff_profiles | staff_type=manager |
| ValetProfile | ✅ | Via staff_profiles | staff_type=valet |
| VALID_ROLES | ✅ | — | + valet, manager |
| FanType | ✅ | — | superfan, super_viewer, common_viewer, common_fan |
| AudienceDemographics | ✅ | ✅ | AudienceDemographicsDB |
| AudienceSegment | ✅ | ✅ | AudienceSegmentDB |
