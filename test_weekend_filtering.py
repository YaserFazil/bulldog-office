#!/usr/bin/env python3
"""
Test script for weekend filtering logic
======================================

This script tests the weekend filtering functionality.
"""

from migrate_to_frappe_hr import FrappeHRMigrator

def test_weekend_filtering():
    """Test the weekend filtering logic with sample data."""
    
    print("🧪 Testing Weekend Filtering Logic")
    print("=" * 50)
    
    # Create migrator instance (without connecting to DB)
    migrator = FrappeHRMigrator("dummy_uri")
    
    # Test cases
    test_cases = [
        # Weekend non-working day (should be filtered out)
        {
            "name": "Saturday non-working",
            "record": {"Day": "SAT", "IN": "", "OUT": ""},
            "expected": True
        },
        {
            "name": "Sunday non-working",
            "record": {"Day": "SUN", "IN": None, "OUT": None},
            "expected": True
        },
        {
            "name": "Saturday with nan values",
            "record": {"Day": "SAT", "IN": "nan", "OUT": "nan"},
            "expected": True
        },
        
        # Weekend working day (should NOT be filtered out)
        {
            "name": "Saturday with work",
            "record": {"Day": "SAT", "IN": "09:00", "OUT": "17:00"},
            "expected": False
        },
        {
            "name": "Sunday with work",
            "record": {"Day": "SUN", "IN": "10:00", "OUT": "16:00"},
            "expected": False
        },
        {
            "name": "Saturday with only IN time",
            "record": {"Day": "SAT", "IN": "09:00", "OUT": ""},
            "expected": False
        },
        
        # Weekday records (should NOT be filtered out)
        {
            "name": "Monday non-working",
            "record": {"Day": "MON", "IN": "", "OUT": ""},
            "expected": False
        },
        {
            "name": "Friday with work",
            "record": {"Day": "FRI", "IN": "09:00", "OUT": "17:00"},
            "expected": False
        },
    ]
    
    print("Running test cases...")
    print()
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases, 1):
        record = test_case["record"]
        expected = test_case["expected"]
        name = test_case["name"]
        
        result = migrator.is_weekend_non_working_day(record)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        
        print(f"Test {i}: {name}")
        print(f"  Record: {record}")
        print(f"  Expected to be filtered: {expected}")
        print(f"  Actual result: {result}")
        print(f"  Status: {status}")
        print()
        
        if result != expected:
            all_passed = False
    
    print("=" * 50)
    if all_passed:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed!")
    
    return all_passed

if __name__ == "__main__":
    test_weekend_filtering()
