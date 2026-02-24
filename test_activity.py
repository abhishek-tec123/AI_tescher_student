#!/usr/bin/env python3
"""
Test script for the activity tracking system.
This script creates some sample activities to test the recent activity API.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from studentProfileDetails.activity_tracker import (
    activity_tracker,
    log_agent_created,
    log_agent_updated,
    log_student_created,
    log_student_updated,
    ActivityType
)
from datetime import datetime, timedelta

def create_sample_activities():
    """Create some sample activities for testing."""
    print("Creating sample activities...")
    
    # Create some agent activities
    log_agent_created(
        agent_id="agent_MATH001",
        agent_name="Advanced Mathematics",
        subject="Mathematics",
        class_name="Class 12"
    )
    
    log_agent_updated(
        agent_id="agent_PHY002",
        agent_name="Physics 101",
        subject="Physics",
        class_name="Class 11",
        changes=["documents", "description"]
    )
    
    # Create some student activities
    log_student_created(
        student_id="std_12345",
        student_name="John Doe",
        class_name="Class 12",
        subject_agent="Advanced Mathematics"
    )
    
    log_student_updated(
        student_id="std_67890",
        student_name="Jane Smith",
        changes=["email", "subject_agent"]
    )
    
    print("✅ Sample activities created successfully!")

def test_recent_activities():
    """Test the recent activities retrieval."""
    print("\nTesting recent activities retrieval...")
    
    activities = activity_tracker.get_recent_activities(limit=10)
    
    print(f"Found {len(activities)} recent activities:")
    for activity in activities:
        print(f"  - {activity['activity_type']}: {activity['description']} ({activity['time_ago']})")
    
    return activities

def test_activity_stats():
    """Test the activity statistics."""
    print("\nTesting activity statistics...")
    
    stats = activity_tracker.get_activity_stats(days_back=7)
    
    print(f"Total activities in last {stats['period_days']} days: {stats['total_activities']}")
    print("By type:")
    for stat in stats['by_type']:
        print(f"  - {stat['activity_type']}: {stat['count']}")
    
    return stats

def main():
    """Main test function."""
    print("🧪 Testing Activity Tracking System")
    print("=" * 50)
    
    try:
        # Create sample activities
        create_sample_activities()
        
        # Test recent activities
        activities = test_recent_activities()
        
        # Test statistics
        stats = test_activity_stats()
        
        print("\n✅ All tests passed!")
        print("\nYou can now test the API endpoints:")
        print("  GET /api/v1/activity/recent")
        print("  GET /api/v1/activity/stats")
        print("  GET /api/v1/activity/activity-types")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
