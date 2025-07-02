#!/usr/bin/env python3

"""
Test script to verify that our program requirements changes work correctly.
"""

import os
import sys
import django

# Add the project root to the Python path
project_root = '/Users/collinpreston/PycharmProjects/mitxonline'
sys.path.insert(0, project_root)

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from courses.models import Program, ProgramRequirement, ProgramRequirementNodeType
from courses.factories import ProgramFactory

def test_program_requirements():
    """Test the new program requirement functionality."""
    print("Testing program requirements...")
    
    # Create test programs
    parent_program = ProgramFactory.create()
    required_program = ProgramFactory.create()
    
    print(f"Created parent program: {parent_program.readable_id}")
    print(f"Created required program: {required_program.readable_id}")
    
    # Test adding a program requirement
    try:
        parent_program.add_program_requirement(required_program)
        print("✓ Successfully added program requirement")
        
        # Test the new property
        required_programs = parent_program.required_programs
        print(f"✓ Required programs: {[p.readable_id for p in required_programs]}")
        
        # Test the node type
        program_requirement = ProgramRequirement.objects.filter(
            program=parent_program,
            required_program=required_program,
            node_type=ProgramRequirementNodeType.PROGRAM
        ).first()
        
        if program_requirement:
            print("✓ Found program requirement node")
            print(f"✓ Node type is PROGRAM: {program_requirement.is_program}")
            print(f"✓ Node is not course: {not program_requirement.is_course}")
        else:
            print("✗ Program requirement node not found")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_program_requirements()
