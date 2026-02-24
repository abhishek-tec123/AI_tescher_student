#!/usr/bin/env python3
"""
Test script that creates activities with realistic time differences.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from studentProfileDetails.activity_tracker import activity_tracker
from datetime import datetime, timedelta
import pymongo

def create_realistic_activities():
    """Create activities with realistic time differences."""
    print("Creating realistic sample activities...")
    
    # Create activities with different timestamps by directly inserting into MongoDB
    if not activity_tracker.connected:
        print("MongoDB not connected - cannot create realistic timestamps")
        return
    
    now = datetime.utcnow()
    
    # Activity 1: 2 hours ago
    activity_1 = {
        "activity_type": "agent_created",
        "target_id": "agent_MATH001",
        "target_name": "Advanced Mathematics",
        "description": "New agent created for Mathematics",
        "metadata": {
            "subject": "Mathematics",
            "class": "Class 12",
            "action": "created"
        },
        "timestamp": now - timedelta(hours=2)
    }
    
    # Activity 2: 1 hour ago
    activity_2 = {
        "activity_type": "student_created",
        "target_id": "std_12345",
        "target_name": "John Doe",
        "description": "New student joined - Advanced Mathematics",
        "metadata": {
            "class": "Class 12",
            "subject_agent": "Advanced Mathematics",
            "action": "created"
        },
        "timestamp": now - timedelta(hours=1)
    }
    
    # Activity 3: 5 minutes ago
    activity_3 = {
        "activity_type": "agent_updated",
        "target_id": "agent_PHY002",
        "target_name": "Physics 101",
        "description": "Agent updated for Physics",
        "metadata": {
            "subject": "Physics",
            "class": "Class 11",
            "changes": ["documents", "description"],
            "action": "updated"
        },
        "timestamp": now - timedelta(minutes=5)
    }
    
    # Activity 4: 30 seconds ago
    activity_4 = {
        "activity_type": "student_updated",
        "target_id": "std_67890",
        "target_name": "Jane Smith",
        "description": "Student profile updated",
        "metadata": {
            "changes": ["email", "subject_agent"],
            "action": "updated"
        },
        "timestamp": now - timedelta(seconds=30)
    }
    
    # Insert activities with custom timestamps
    activities = [activity_1, activity_2, activity_3, activity_4]
    
    for activity in activities:
        result = activity_tracker.activities.insert_one(activity)
        print(f"✅ Created activity: {activity['description']} at {activity['timestamp']}")
    
    print(f"\nCreated {len(activities)} activities with realistic timestamps!")

def test_time_formatting():
    """Test the time formatting with different intervals."""
    print("\nTesting time formatting...")
    
    now = datetime.utcnow()
    
    test_cases = [
        (now - timedelta(seconds=30), "30 seconds ago"),
        (now - timedelta(minutes=5), "5 mins ago"),
        (now - timedelta(minutes=65), "1 hours ago"),
        (now - timedelta(hours=2), "2 hours ago"),
        (now - timedelta(days=1), "1 days ago"),
        (now - timedelta(days=3), "3 days ago"),
    ]
    
    for test_time, expected_pattern in test_cases:
        time_diff = now - test_time
        
        if time_diff.total_seconds() < 60:
            time_ago = f"{int(time_diff.total_seconds())} seconds ago"
        elif time_diff.total_seconds() < 3600:
            time_ago = f"{int(time_diff.total_seconds() / 60)} mins ago"
        elif time_diff.total_seconds() < 86400:
            time_ago = f"{int(time_diff.total_seconds() / 3600)} hours ago"
        else:
            time_ago = f"{int(time_diff.total_seconds() / 86400)} days ago"
        
        print(f"  {test_time} -> {time_ago}")

def main():
    """Main test function."""
    print("🧪 Testing Realistic Activity Time Formatting")
    print("=" * 50)
    
    try:
        # Test time formatting logic
        test_time_formatting()
        
        # Create realistic activities
        create_realistic_activities()
        
        # Test recent activities retrieval
        print("\nTesting recent activities retrieval...")
        activities = activity_tracker.get_recent_activities(limit=10)
        
        print(f"\nFound {len(activities)} recent activities:")
        for activity in activities:
            print(f"  - {activity['activity_type']}: {activity['description']} ({activity['time_ago']})")
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
