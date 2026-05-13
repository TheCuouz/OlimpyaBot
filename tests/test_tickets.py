import unittest
import json
import os
import tempfile
import shutil
from datetime import datetime
from utils.ticket_manager import TicketManager
from utils.ticket_utils import get_channel_name


class TestTicketManager(unittest.TestCase):
    """Unit tests for TicketManager class"""
    
    def setUp(self):
        """Create a temporary directory for test data"""
        self.test_dir = tempfile.mkdtemp()
        self.data_file = os.path.join(self.test_dir, "test_tickets.json")
        self.manager = TicketManager(self.data_file)
    
    def tearDown(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.test_dir)
    
    def test_create_ticket(self):
        """Test creating a ticket and verifying it's saved"""
        ticket_id = self.manager.create_ticket(
            creator_id=123456,
            creator_name="TestUser",
            category="Bug",
            priority="High",
            title="Test Bug",
            description="This is a test bug report"
        )
        
        self.assertEqual(ticket_id, "T001")
        self.assertEqual(len(self.manager.data["tickets"]), 1)
        
        ticket = self.manager.get_ticket(ticket_id)
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket["title"], "Test Bug")
        self.assertEqual(ticket["creator_name"], "TestUser")
        self.assertEqual(ticket["status"], "open")
        self.assertIsNone(ticket["assigned_to"])
    
    def test_ticket_counter_increments(self):
        """Test that ticket counter increments correctly (T001, T002, etc)"""
        id1 = self.manager.create_ticket(
            creator_id=111, creator_name="User1",
            category="Bug", priority="Low",
            title="Ticket 1", description="First"
        )
        id2 = self.manager.create_ticket(
            creator_id=222, creator_name="User2",
            category="Feature", priority="Medium",
            title="Ticket 2", description="Second"
        )
        id3 = self.manager.create_ticket(
            creator_id=333, creator_name="User3",
            category="Support", priority="High",
            title="Ticket 3", description="Third"
        )
        
        self.assertEqual(id1, "T001")
        self.assertEqual(id2, "T002")
        self.assertEqual(id3, "T003")
        self.assertEqual(self.manager.data["counter"], 3)
    
    def test_close_ticket(self):
        """Test closing a ticket and verifying status changes"""
        ticket_id = self.manager.create_ticket(
            creator_id=123, creator_name="TestUser",
            category="Bug", priority="High",
            title="Test", description="Test"
        )
        
        self.manager.close_ticket(ticket_id)
        ticket = self.manager.get_ticket(ticket_id)
        
        self.assertEqual(ticket["status"], "closed")
        self.assertIsNotNone(ticket["closed_at"])
    
    def test_reopen_ticket(self):
        """Test reopening a closed ticket"""
        ticket_id = self.manager.create_ticket(
            creator_id=123, creator_name="TestUser",
            category="Bug", priority="High",
            title="Test", description="Test"
        )
        
        self.manager.close_ticket(ticket_id)
        self.manager.reopen_ticket(ticket_id)
        
        ticket = self.manager.get_ticket(ticket_id)
        self.assertEqual(ticket["status"], "reopened")
        self.assertIsNone(ticket["closed_at"])
    
    def test_assign_ticket(self):
        """Test assigning a ticket to staff"""
        ticket_id = self.manager.create_ticket(
            creator_id=123, creator_name="TestUser",
            category="Bug", priority="High",
            title="Test", description="Test"
        )
        
        self.manager.assign_ticket(ticket_id, 999, "StaffMember")
        ticket = self.manager.get_ticket(ticket_id)
        
        self.assertEqual(ticket["assigned_to"], 999)
        self.assertEqual(ticket["assigned_to_name"], "StaffMember")
    
    def test_add_note(self):
        """Test adding notes to a ticket"""
        ticket_id = self.manager.create_ticket(
            creator_id=123, creator_name="TestUser",
            category="Bug", priority="High",
            title="Test", description="Test"
        )
        
        self.manager.add_note(ticket_id, "Reviewer", 456, "Looking into this")
        self.manager.add_note(ticket_id, "Reviewer", 456, "Found the issue")
        
        ticket = self.manager.get_ticket(ticket_id)
        self.assertEqual(len(ticket["notes"]), 2)
        self.assertEqual(ticket["notes"][0]["author"], "Reviewer")
        self.assertEqual(ticket["notes"][0]["content"], "Looking into this")
        self.assertEqual(ticket["notes"][1]["content"], "Found the issue")
    
    def test_list_tickets(self):
        """Test filtering tickets by status"""
        # Create multiple tickets
        id1 = self.manager.create_ticket(
            creator_id=1, creator_name="User1",
            category="Bug", priority="Low",
            title="Ticket 1", description="First"
        )
        id2 = self.manager.create_ticket(
            creator_id=2, creator_name="User2",
            category="Feature", priority="Medium",
            title="Ticket 2", description="Second"
        )
        id3 = self.manager.create_ticket(
            creator_id=3, creator_name="User3",
            category="Support", priority="High",
            title="Ticket 3", description="Third"
        )
        
        # Close one ticket
        self.manager.close_ticket(id1)
        
        # Test list all
        all_tickets = self.manager.list_tickets()
        self.assertEqual(len(all_tickets), 3)
        
        # Test filter by open
        open_tickets = self.manager.list_tickets(status="open")
        self.assertEqual(len(open_tickets), 2)
        self.assertIn(id2, [t["ticket_id"] for t in open_tickets])
        
        # Test filter by closed
        closed_tickets = self.manager.list_tickets(status="closed")
        self.assertEqual(len(closed_tickets), 1)
        self.assertEqual(closed_tickets[0]["ticket_id"], id1)
    
    def test_get_nonexistent_ticket(self):
        """Test getting a ticket that doesn't exist returns None"""
        result = self.manager.get_ticket("T999")
        self.assertIsNone(result)
    
    def test_persistence(self):
        """Test that data persists after manager restart"""
        # Create tickets with first manager instance
        id1 = self.manager.create_ticket(
            creator_id=111, creator_name="User1",
            category="Bug", priority="Low",
            title="Persistent Ticket", description="Should survive restart"
        )
        self.manager.assign_ticket(id1, 999, "StaffMember")
        self.manager.add_note(id1, "Reviewer", 456, "Important note")
        
        # Create new manager instance (simulating restart)
        new_manager = TicketManager(self.data_file)
        
        # Verify data was loaded
        self.assertEqual(len(new_manager.data["tickets"]), 1)
        self.assertEqual(new_manager.data["counter"], 1)
        
        # Verify ticket details
        ticket = new_manager.get_ticket(id1)
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket["title"], "Persistent Ticket")
        self.assertEqual(ticket["assigned_to"], 999)
        self.assertEqual(len(ticket["notes"]), 1)
        self.assertEqual(ticket["notes"][0]["content"], "Important note")
    
    def test_update_ticket(self):
        """Test updating arbitrary ticket fields"""
        ticket_id = self.manager.create_ticket(
            creator_id=123, creator_name="TestUser",
            category="Bug", priority="High",
            title="Test", description="Test"
        )
        
        self.manager.update_ticket(ticket_id, {
            "priority": "Critical",
            "category": "Security"
        })
        
        ticket = self.manager.get_ticket(ticket_id)
        self.assertEqual(ticket["priority"], "Critical")
        self.assertEqual(ticket["category"], "Security")
    
    def test_timestamp_format(self):
        """Test that timestamps are in ISO format"""
        ticket_id = self.manager.create_ticket(
            creator_id=123, creator_name="TestUser",
            category="Bug", priority="High",
            title="Test", description="Test"
        )
        
        ticket = self.manager.get_ticket(ticket_id)
        
        # Verify created_at is valid ISO format
        try:
            datetime.fromisoformat(ticket["created_at"])
        except ValueError:
            self.fail("created_at is not in ISO format")
    
    def test_note_timestamp_format(self):
        """Test that note timestamps are in ISO format"""
        ticket_id = self.manager.create_ticket(
            creator_id=123, creator_name="TestUser",
            category="Bug", priority="High",
            title="Test", description="Test"
        )
        
        self.manager.add_note(ticket_id, "Reviewer", 456, "Test note")
        ticket = self.manager.get_ticket(ticket_id)
        
        note = ticket["notes"][0]
        try:
            datetime.fromisoformat(note["timestamp"])
        except ValueError:
            self.fail("Note timestamp is not in ISO format")


class TestTicketUtils(unittest.TestCase):
    """Unit tests for ticket utility functions"""
    
    def test_channel_name_generation(self):
        """Test that channel name format is correct"""
        channel_name = get_channel_name("T001", "Test Ticket Title")
        
        self.assertIn("ticket-T001", channel_name)
        self.assertIn("test", channel_name)
        self.assertIn("ticket", channel_name)
        self.assertTrue(channel_name.startswith("ticket-"))
    
    def test_channel_name_sanitization(self):
        """Test that special characters are removed from channel names"""
        test_cases = [
            ("T001", "Hello@World#123!", "ticket-T001-helloworld123"),
            ("T002", "Bug$$$Report!", "ticket-T002-bugreport"),
            ("T003", "Feature-Request", "ticket-T003-feature-request"),
            ("T004", "Support & Help", "ticket-T004-support--help"),
        ]

        for ticket_id, title, expected in test_cases:
            result = get_channel_name(ticket_id, title)
            self.assertEqual(result, expected)
    
    def test_channel_name_truncation(self):
        """Test that very long titles are truncated properly"""
        long_title = "This is a very long ticket title that exceeds the maximum length"
        channel_name = get_channel_name("T001", long_title)
        
        # Channel name should not be excessively long
        self.assertLessEqual(len(channel_name), 60)
        self.assertTrue(channel_name.startswith("ticket-T001"))
    
    def test_channel_name_lowercase(self):
        """Test that title part of channel name is lowercase"""
        channel_name = get_channel_name("T001", "UPPERCASE TITLE")

        # The title portion should be lowercase, though ticket_id preserves case
        self.assertIn("uppercase-title", channel_name)
        # Full name may contain uppercase T from ticket ID
        self.assertTrue(channel_name.startswith("ticket-T001"))
    
    def test_channel_name_spaces_to_dashes(self):
        """Test that spaces are converted to dashes"""
        channel_name = get_channel_name("T001", "Multiple Word Title")
        
        self.assertNotIn(" ", channel_name)
        self.assertIn("-", channel_name)
    
    def test_channel_name_empty_title_fallback(self):
        """Test that empty/invalid titles fall back to 'ticket'"""
        # Title with only special characters
        channel_name = get_channel_name("T001", "@#$%^&*()")
        
        self.assertIn("ticket", channel_name)
        self.assertTrue(channel_name.startswith("ticket-"))


if __name__ == "__main__":
    unittest.main()
