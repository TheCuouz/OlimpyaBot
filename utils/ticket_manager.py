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
