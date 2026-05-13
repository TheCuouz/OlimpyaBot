# Ticket System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a complete Discord ticket system with button-triggered modals, private channels, and persistent JSON storage.

**Architecture:** Users click a button to open a modal form (description, category, priority), which creates a private channel. The system stores ticket data in JSON, manages permissions, and provides staff with action buttons (close, assign, change priority, add notes).

**Tech Stack:** discord.py 2.4.0, Python 3.8+, JSON for persistence

---

## Task 1: Update Configuration

**Files:**
- Modify: `config.py`

Agregar configuración de tickets al archivo de config centralizado.

- [ ] **Step 1: Open config.py and add ticket configuration**

```python
# At the end of config.py, add:

TICKET_CONFIG = {
    "enabled": True,
    "categories": ["Bug", "Support", "Feature Request"],
    "priorities": ["Low", "Medium", "High", "Critical"],
    "staff_role_name": "Staff",
    "data_file": "data/tickets.json",
}
```

- [ ] **Step 2: Commit**

```bash
git add config.py
git commit -m "config: add ticket system configuration"
```

---

## Task 2: Create TicketManager Class

**Files:**
- Create: `utils/ticket_manager.py`

Clase para manejar persistencia de tickets en JSON. Soporta CRUD operations, notas, y cambios de estado.

- [ ] **Step 1: Create the file with class definition**

Create `utils/ticket_manager.py` with full TicketManager implementation (see code block below)

```python
import json
import os
from datetime import datetime
from typing import Optional, Dict, List
from utils.logger import logger

class TicketManager:
    def __init__(self, data_file: str):
        self.data_file = data_file
        self.data = {"tickets": [], "counter": 0}
        self._ensure_file_exists()
        self._load_data()
    
    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, "w") as f:
                json.dump(self.data, f, indent=2)
            logger.info(f"Created ticket data file: {self.data_file}")
    
    def _load_data(self):
        try:
            with open(self.data_file, "r") as f:
                self.data = json.load(f)
            logger.info(f"Loaded {len(self.data['tickets'])} tickets from JSON")
        except json.JSONDecodeError:
            logger.error("Corrupted JSON file, creating backup and new file")
            backup_file = f"{self.data_file}.backup"
            os.rename(self.data_file, backup_file)
            self.data = {"tickets": [], "counter": 0}
            self._save_data()
    
    def _save_data(self):
        try:
            with open(self.data_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save ticket data: {e}")
            raise
    
    def create_ticket(self, creator_id: int, creator_name: str, 
                     category: str, priority: str, 
                     title: str, description: str) -> str:
        self.data["counter"] += 1
        ticket_id = f"T{self.data['counter']:03d}"
        
        ticket = {
            "ticket_id": ticket_id,
            "channel_id": None,
            "creator_id": creator_id,
            "creator_name": creator_name,
            "status": "open",
            "category": category,
            "priority": priority,
            "title": title,
            "description": description,
            "assigned_to": None,
            "assigned_to_name": None,
            "created_at": datetime.utcnow().isoformat(),
            "closed_at": None,
            "notes": [],
        }
        
        self.data["tickets"].append(ticket)
        self._save_data()
        logger.info(f"Created ticket {ticket_id}")
        return ticket_id
    
    def get_ticket(self, ticket_id: str) -> Optional[Dict]:
        for ticket in self.data["tickets"]:
            if ticket["ticket_id"] == ticket_id:
                return ticket
        return None
    
    def update_ticket(self, ticket_id: str, updates: Dict):
        ticket = self.get_ticket(ticket_id)
        if ticket:
            ticket.update(updates)
            self._save_data()
            logger.info(f"Updated ticket {ticket_id}: {updates}")
    
    def add_note(self, ticket_id: str, author: str, author_id: int, content: str):
        ticket = self.get_ticket(ticket_id)
        if ticket:
            note = {
                "author": author,
                "author_id": author_id,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            }
            ticket["notes"].append(note)
            self._save_data()
            logger.info(f"Added note to ticket {ticket_id}")
    
    def close_ticket(self, ticket_id: str):
        ticket = self.get_ticket(ticket_id)
        if ticket:
            ticket["status"] = "closed"
            ticket["closed_at"] = datetime.utcnow().isoformat()
            self._save_data()
            logger.info(f"Closed ticket {ticket_id}")
    
    def reopen_ticket(self, ticket_id: str):
        ticket = self.get_ticket(ticket_id)
        if ticket:
            ticket["status"] = "reopened"
            ticket["closed_at"] = None
            self._save_data()
            logger.info(f"Reopened ticket {ticket_id}")
    
    def assign_ticket(self, ticket_id: str, staff_id: int, staff_name: str):
        ticket = self.get_ticket(ticket_id)
        if ticket:
            ticket["assigned_to"] = staff_id
            ticket["assigned_to_name"] = staff_name
            self._save_data()
            logger.info(f"Assigned ticket {ticket_id} to {staff_name}")
    
    def list_tickets(self, status: Optional[str] = None) -> List[Dict]:
        if status:
            return [t for t in self.data["tickets"] if t["status"] == status]
        return self.data["tickets"]
```

- [ ] **Step 2: Syntax check**

```bash
python -m py_compile utils/ticket_manager.py
```

Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add utils/ticket_manager.py
git commit -m "feat: add TicketManager for JSON persistence"
```

---

## Task 3: Create Ticket Utilities

**Files:**
- Create: `utils/ticket_utils.py`

Helper functions para generar embeds, crear canales, y verificar permisos.

- [ ] **Step 1: Create file with utility functions**

```python
import discord
from datetime import datetime
from typing import Optional

def create_ticket_embed(ticket: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"Ticket #{ticket['ticket_id']} - {ticket['title']}",
        description=ticket['description'],
        color=discord.Color.blue()
    )
    embed.add_field(name="Creator", value=f"<@{ticket['creator_id']}>", inline=True)
    embed.add_field(name="Category", value=ticket['category'], inline=True)
    embed.add_field(name="Priority", value=ticket['priority'], inline=True)
    status_color = {"open": "🟢 Open", "closed": "🔴 Closed", "reopened": "🟡 Reopened"}
    embed.add_field(name="Status", value=status_color.get(ticket['status'], ticket['status']), inline=True)
    assigned = ticket.get('assigned_to_name') or "Unassigned"
    embed.add_field(name="Assigned To", value=assigned, inline=True)
    created_at = datetime.fromisoformat(ticket['created_at']).strftime("%Y-%m-%d %H:%M UTC")
    embed.add_field(name="Created", value=created_at, inline=False)
    if ticket['notes']:
        notes_text = f"{len(ticket['notes'])} note(s)"
        embed.add_field(name="Notes", value=notes_text, inline=False)
    embed.set_footer(text="Use buttons below to manage this ticket")
    return embed

def create_setup_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📋 Create a Support Ticket",
        description="Click the button below to create a new support ticket. You'll be asked for a description, category, and priority level.",
        color=discord.Color.blue()
    )
    embed.set_footer(text="OlimpyaBot Ticket System")
    return embed

def create_action_embed(action: str, performed_by: str) -> discord.Embed:
    embed = discord.Embed(
        title="✅ Ticket Updated",
        description=f"Action: {action} by {performed_by}",
        color=discord.Color.green()
    )
    embed.timestamp = datetime.utcnow()
    return embed

def get_channel_name(ticket_id: str, title: str) -> str:
    sanitized = "".join(c if c.isalnum() or c == "-" else "" for c in title.lower().replace(" ", "-"))
    sanitized = sanitized[:20] if sanitized else "ticket"
    return f"ticket-{ticket_id}-{sanitized}"

async def create_ticket_channel(guild: discord.Guild, ticket_id: str, 
                               title: str, creator: discord.Member, 
                               staff_role: Optional[discord.Role] = None) -> Optional[discord.TextChannel]:
    channel_name = get_channel_name(ticket_id, title)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        creator: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    try:
        channel = await guild.create_text_channel(
            channel_name,
            overwrites=overwrites,
            topic=f"Ticket {ticket_id} - Created by {creator.name}"
        )
        return channel
    except Exception as e:
        return None

async def archive_channel(channel: discord.TextChannel):
    try:
        new_name = f"✅-{channel.name}"
        if len(new_name) > 100:
            new_name = f"✅-{channel.name[-95:]}"
        await channel.edit(name=new_name)
    except Exception as e:
        pass

def get_staff_role(guild: discord.Guild, staff_role_name: str) -> Optional[discord.Role]:
    for role in guild.roles:
        if role.name.lower() == staff_role_name.lower():
            return role
    return None

def user_is_staff(member: discord.Member, staff_role: Optional[discord.Role]) -> bool:
    if not staff_role:
        return member.guild_permissions.administrator
    return staff_role in member.roles or member.guild_permissions.administrator
```

- [ ] **Step 2: Syntax check**

```bash
python -m py_compile utils/ticket_utils.py
```

- [ ] **Step 3: Commit**

```bash
git add utils/ticket_utils.py
git commit -m "feat: add ticket utilities for embeds and channels"
```

---

## Task 4: Create Main Tickets Cog

**Files:**
- Create: `cogs/tickets.py`

Cog principal que integra todo: modal, buttons, setup command.

- [ ] **Step 1: Create the tickets cog**

(Due to size, implement the full cog from the design doc - includes TicketModal, Tickets class with all methods)

- [ ] **Step 2: Syntax check**

```bash
python -m py_compile cogs/tickets.py
```

- [ ] **Step 3: Commit**

```bash
git add cogs/tickets.py
git commit -m "feat: add tickets cog with modal and button handling"
```

---

## Task 5: Initialize Data Directory

**Files:**
- Create: `data/tickets.json`

- [ ] **Step 1: Create directory and file**

```bash
mkdir -p data
echo '{"tickets": [], "counter": 0}' > data/tickets.json
```

- [ ] **Step 2: Commit**

```bash
git add data/tickets.json
git commit -m "data: initialize tickets data file"
```

---

## Task 6: Create Tests

**Files:**
- Create: `tests/test_tickets.py`

Unit tests para TicketManager y utilidades.

- [ ] **Step 1: Create test file with TicketManager tests**

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_tickets.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_tickets.py
git commit -m "test: add unit tests for ticket system"
```

---

## Task 7: Update .gitignore and Create .gitkeep

**Files:**
- Modify: `.gitignore`
- Create: `data/.gitkeep`

- [ ] **Step 1: Update .gitignore**

Add to end of file:
```
# Ticket data
data/*.json
!data/.gitkeep
```

- [ ] **Step 2: Create .gitkeep**

```bash
touch data/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore data/.gitkeep
git commit -m "build: update gitignore for data directory"
```

---

## Task 8: Manual Testing

**Files:** None

- [ ] **Step 1: Start bot**

```bash
python main.py
```

- [ ] **Step 2: Run `/setup-tickets` in Discord**

- [ ] **Step 3: Click Create Ticket button**

- [ ] **Step 4: Fill modal and submit**

- [ ] **Step 5: Verify ticket channel created**

- [ ] **Step 6: Test ticket buttons**

- [ ] **Step 7: Verify JSON updated**

```bash
cat data/tickets.json
```

---

## Files Summary

**Created:**
- `cogs/tickets.py`
- `utils/ticket_manager.py`
- `utils/ticket_utils.py`
- `data/tickets.json`
- `tests/test_tickets.py`

**Modified:**
- `config.py`
- `.gitignore`

**Total: 8 tasks, ~500 lines of code**

