# OlimpyaBot Ticket System Design

**Date:** 2026-05-14  
**Status:** Design Approved  
**Owner:** Development Team

---

## Executive Summary

A professional Discord ticket system for managing user support requests. Users create tickets by clicking a button on a setup message, filling a modal form with description/category/priority. Each ticket gets a private channel where users and staff collaborate. Staff can manage tickets (assign, change priority, reopen, close). All data persists in JSON for simplicity.

---

## 1. Overview

### Purpose
Enable users to create support tickets directly in Discord without complex commands. Provide staff with tools to manage, track, and resolve tickets efficiently.

### Scope
- Create tickets via button + modal UI
- Private channels per ticket
- Full ticket lifecycle (create → manage → close → archive)
- Persistent storage in JSON
- Role-based permissions

### Success Criteria
- Users can create ticket in < 30 seconds (button click → modal → done)
- Tickets stored persistently, survive bot restart
- All staff actions logged and visible
- Channels auto-archived when closed
- Zero data loss on crashes (validate JSON at startup)

---

## 2. Architecture

### Components

#### 2.1 Core Cog: `cogs/tickets.py`
Main module orchestrating all ticket operations.

**Responsibilities:**
- Admin command `/setup-tickets` → sends setup message with button
- Modal form listener → receives user input
- Channel creation and management
- Button listeners for ticket actions
- JSON synchronization

#### 2.2 Utilities: `utils/ticket_utils.py`
Helper functions for ticket operations.

**Functions:**
- `create_channel()` → creates private channel with permissions
- `generate_embed()` → creates formatted ticket embeds
- `validate_permissions()` → checks user roles
- `archive_channel()` → marks channel read-only

#### 2.3 Data Layer: `utils/ticket_manager.py`
Handles JSON read/write operations.

**Methods:**
- `create_ticket(data)` → saves new ticket, returns ID
- `update_ticket(ticket_id, changes)` → modifies ticket state
- `get_ticket(ticket_id)` → retrieves ticket data
- `list_tickets(filters)` → query tickets
- `add_note(ticket_id, note)` → appends note to ticket
- `validate_json()` → checks integrity at startup

#### 2.4 Data Storage: `data/tickets.json`
Single JSON file containing all ticket data.

---

## 3. Data Model

### Ticket Object Structure
```json
{
  "ticket_id": "T001",
  "channel_id": 1234567890,
  "creator_id": 9876543210,
  "creator_name": "UserName",
  "status": "open",
  "category": "Bug",
  "priority": "High",
  "title": "Brief description",
  "description": "Full details from modal",
  "assigned_to": 1111111111,
  "assigned_to_name": "StaffName",
  "created_at": "2026-05-14T10:30:00",
  "closed_at": null,
  "notes": [
    {
      "author": "StaffName",
      "author_id": 1111111111,
      "content": "Note text",
      "timestamp": "2026-05-14T11:00:00"
    }
  ]
}
```

### Valid Values

**Status:** `open`, `closed`, `reopened`

**Categories:** (configurable in `config.py`)
- Bug
- Support
- Feature Request

**Priorities:** (ordered by severity)
- Low
- Medium
- High
- Critical

### File Structure
```json
{
  "tickets": [
    { /* ticket objects */ }
  ],
  "counter": 1
}
```

The `counter` tracks the next ticket ID (T001, T002, etc.).

---

## 4. User Flows

### 4.1 Create Ticket Flow

**Actors:** User, Bot

**Steps:**
1. Admin runs `/setup-tickets` in designated channel
2. Bot sends embed with "Create Ticket" button
3. User clicks button
4. Discord opens modal form with fields:
   - **Description** (required, text input, max 1024 chars)
   - **Category** (required, select menu: Bug/Support/Feature Request)
   - **Priority** (required, select menu: Low/Medium/High/Critical)
5. User submits modal
6. Bot:
   - Generates ticket ID (T001, T002...)
   - Creates private channel: `ticket-T001-brief-description`
   - Sets permissions: creator + staff can see, others cannot
   - Saves ticket to `data/tickets.json`
   - Sends confirmation embed in new channel
   - Sends buttons for ticket actions

**Error Handling:**
- Modal timeout/cancel → DM user: "Ticket creation cancelled"
- Channel creation fails → Log error, DM user: "Unable to create channel, contact staff"
- JSON write fails → Log error, alert staff in admin channel

### 4.2 Manage Ticket Flow

**Actors:** Creator, Staff

**Actions in Ticket Channel:**

| Action | Trigger | Who | Effect |
|--------|---------|-----|--------|
| Cerrar | Button | Creator, Staff | Set status="closed", archive channel |
| Reopener | Button | Staff | Set status="reopened", unarchive |
| Asignar | Button | Staff | Assign ticket to staff member, send confirmation |
| Cambiar Prioridad | Button | Staff | Select new priority, update JSON |
| Agregar Nota | Button | Anyone | Add timestamped note visible to all |

**Channel Embed Updates:**
After each action, bot updates the main ticket embed showing current state.

### 4.3 Close & Archive Flow

**Steps:**
1. Creator or Staff clicks "Cerrar"
2. Bot:
   - Sets status="closed" in JSON
   - Archives channel (read-only for non-staff)
   - Sends closure embed with timestamp and summary
   - Logs action in `logs/`

**After Closure:**
- Staff can still view and add notes (read-only for creator)
- Channel name prefixed with ✅ (or similar) to indicate closed

---

## 5. UI Components

### Setup Message Embed
```
Title: "Create a Support Ticket"
Description: "Click the button below to create a new support ticket.
You'll be asked for a description, category, and priority level.
Our team will respond as soon as possible."
Color: Blue
Button: "Create Ticket" (blue style)
```

### Ticket Channel Embed
```
Title: "Ticket #T001 - Brief Description"
Fields:
  - Creator: @User
  - Category: Bug
  - Priority: High
  - Status: Open
  - Assigned To: @Staff (or "Unassigned")
  - Created: 2026-05-14 10:30 UTC
Description: Full ticket description text

Buttons: [Close] [Reopen] [Assign] [Priority] [Note]
```

### Action Confirmation Embed
```
Title: "✅ Ticket Updated"
Content: "Action performed: Assigned to @Staff by @Staff2"
Timestamp shown
```

---

## 6. Permissions & Access Control

### Channel Permissions (Private)

**Creator:**
- Read messages
- Send messages
- Full ticket lifecycle control (close own ticket)

**Staff Role:**
- Read messages
- Send messages
- Manage ticket (assign, reopen, priority, notes)
- Can close any ticket

**Everyone Else:**
- No access (channel is private)

### Action Permissions

| Action | Allowed For |
|--------|------------|
| Close Ticket | Creator (own), Staff (any) |
| Reopen Ticket | Staff only |
| Assign Ticket | Staff only |
| Change Priority | Staff only |
| Add Note | Anyone in channel |

---

## 7. Data Persistence

### Storage Strategy
- All data stored in `data/tickets.json`
- Changes written immediately (not batched)
- File validated on bot startup
- Automatic backup: on startup, copy previous version to `data/tickets.backup.json`

### Validation
On bot startup:
- Check `data/tickets.json` exists
- Parse JSON for syntax errors
- Verify required fields in all tickets
- Log warnings for malformed entries
- Create backup of current state

### Recovery
- If JSON corrupted: restore from `.backup.json`
- If both corrupt: create empty `tickets.json`
- Log all recovery actions

---

## 8. Error Handling

### User Errors
- **Timeout on modal:** DM user "Ticket creation cancelled. Please try again."
- **Invalid input:** Validate in modal (Discord enforces required fields)
- **No permission to view ticket:** Show error message

### System Errors
- **Channel creation fails:** Log error, DM creator "Unable to create channel", notify staff channel
- **JSON write fails:** Log error, retry up to 3 times, alert staff if persistent
- **Missing staff role:** Log warning, show error in ticket (staff features unavailable)
- **Archive fails:** Log error, keep channel visible, alert staff

### Logging
- All errors logged to `logs/bot_*.log`
- Format: `[TICKET] [ERROR] TicketID: Error description`
- Staff notified via admin channel for critical errors

---

## 9. Configuration

### In `config.py`
```python
TICKET_SETTINGS = {
    "enabled": True,
    "categories": ["Bug", "Support", "Feature Request"],
    "priorities": ["Low", "Medium", "High", "Critical"],
    "staff_role": "Staff",  # Role name or ID
    "admin_channel": None,  # Channel for admin notifications
    "archive_on_close": True,
}
```

### Admin Commands
- `/setup-tickets` → Send setup message with create button
- `/tickets-stats` → Show ticket statistics (open, closed, by category)
- `/tickets-list` → List all open tickets

---

## 10. Testing Strategy

### Unit Tests
- TicketManager JSON operations (create, read, update)
- Ticket validation (required fields, valid enums)
- Permission checks

### Integration Tests
- Full create ticket flow (button → modal → channel creation)
- Ticket actions (close, reopen, assign)
- Permission enforcement

### Manual Testing
- Create ticket through UI
- Test all buttons in ticket channel
- Verify permissions (creator vs staff vs other user)
- Close ticket, verify archive
- Restart bot, verify data persists

---

## 11. Future Enhancements (Out of Scope)

- Database migration (SQLite/PostgreSQL)
- Ticket statistics dashboard
- Automatic ticket assignment logic
- Ticket templates
- SLA tracking (response time)
- Integration with external ticketing systems

---

## 12. Success Metrics

- Users create tickets without errors
- Data persists across bot restarts
- Staff can manage tickets intuitively
- All operations logged and auditable
- No data loss in any scenario

---

## Appendix: Comparison with Original Java Bot

The original Java bot had:
- Simple message listeners
- Basic logging to stdout
- Single command response

The ticket system adds:
- Interactive UI (buttons, modals)
- Complex state management (ticket lifecycle)
- Persistent storage (JSON)
- Role-based permissions
- Channel management
- Comprehensive logging

This represents a significant feature expansion while maintaining the bot's modular architecture.
