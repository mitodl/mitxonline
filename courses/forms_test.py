"""Tests for course forms"""

import pytest

from courses.factories import ProgramFactory
from courses.forms import ProgramAdminForm
from courses.models import ProgramRequirement, ProgramRequirementNodeType

pytestmark = [pytest.mark.django_db]


def test_program_admin_form_creates_default_sections_for_new_program():
    """
    ProgramAdminForm should create default Required and Elective sections for new programs
    """
    form = ProgramAdminForm()
    
    requirements = form.initial["requirements"]
    assert len(requirements) == 2
    
    # Check Required Courses section
    required_section = requirements[0]
    assert required_section["data"]["title"] == "Required Courses"
    assert required_section["data"]["operator"] == ProgramRequirement.Operator.ALL_OF.value
    assert required_section["data"]["elective_flag"] is False
    assert required_section["children"] == []
    
    # Check Elective Courses section
    elective_section = requirements[1]
    assert elective_section["data"]["title"] == "Elective Courses"
    assert elective_section["data"]["operator"] == ProgramRequirement.Operator.MIN_NUMBER_OF.value
    assert elective_section["data"]["elective_flag"] is True
    assert elective_section["data"]["operator_value"] == 1
    assert elective_section["children"] == []


def test_program_admin_form_recreates_missing_required_section():
    """
    ProgramAdminForm should recreate the Required Courses section if it's missing
    """
    program = ProgramFactory()
    root = program.get_requirements_root()
    
    # Create only an Elective Courses section
    elective_section = root.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        title="Elective Courses",
        operator_value=1,
        elective_flag=True,
    )
    
    form = ProgramAdminForm(instance=program)
    requirements = form.initial["requirements"]
    
    # Should have 2 sections now (required section should be added)
    assert len(requirements) == 2
    
    # Check that Required Courses section was added
    required_section = requirements[0]
    assert required_section["data"]["title"] == "Required Courses"
    assert required_section["data"]["operator"] == ProgramRequirement.Operator.ALL_OF.value
    assert required_section["data"]["elective_flag"] is False
    
    # Check that Elective Courses section still exists
    elective_section = requirements[1]
    assert elective_section["data"]["title"] == "Elective Courses"
    assert elective_section["data"]["operator"] == ProgramRequirement.Operator.MIN_NUMBER_OF.value
    assert elective_section["data"]["elective_flag"] is True


def test_program_admin_form_recreates_missing_elective_section():
    """
    ProgramAdminForm should recreate the Elective Courses section if it's missing
    """
    program = ProgramFactory()
    root = program.get_requirements_root()
    
    # Create only a Required Courses section
    required_section = root.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
        elective_flag=False,
    )
    
    form = ProgramAdminForm(instance=program)
    requirements = form.initial["requirements"]
    
    # Should have 2 sections now (elective section should be added)
    assert len(requirements) == 2
    
    # Check that Required Courses section still exists
    required_section = requirements[0]
    assert required_section["data"]["title"] == "Required Courses"
    assert required_section["data"]["operator"] == ProgramRequirement.Operator.ALL_OF.value
    assert required_section["data"]["elective_flag"] is False
    
    # Check that Elective Courses section was added
    elective_section = requirements[1]
    assert elective_section["data"]["title"] == "Elective Courses"
    assert elective_section["data"]["operator"] == ProgramRequirement.Operator.MIN_NUMBER_OF.value
    assert elective_section["data"]["elective_flag"] is True
    assert elective_section["data"]["operator_value"] == 1


def test_program_admin_form_recreates_both_missing_sections():
    """
    ProgramAdminForm should recreate both sections if both are missing
    """
    program = ProgramFactory()
    root = program.get_requirements_root()
    
    # Create a custom section that's not a default section
    custom_section = root.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        title="Custom Section",
        operator_value=2,
        elective_flag=False,
    )
    
    form = ProgramAdminForm(instance=program)
    requirements = form.initial["requirements"]
    
    # Should have 3 sections now (both default sections should be added)
    assert len(requirements) == 3
    
    # Check that Required Courses section was added (should be first)
    required_section = requirements[0]
    assert required_section["data"]["title"] == "Required Courses"
    assert required_section["data"]["operator"] == ProgramRequirement.Operator.ALL_OF.value
    assert required_section["data"]["elective_flag"] is False
    
    # Check that custom section still exists
    custom_found = False
    elective_found = False
    for section in requirements[1:]:  # Skip the first (required) section
        if section["data"]["title"] == "Custom Section":
            assert section["data"]["operator"] == ProgramRequirement.Operator.MIN_NUMBER_OF.value
            assert section["data"]["operator_value"] == 2
            custom_found = True
        elif section["data"]["title"] == "Elective Courses":
            assert section["data"]["operator"] == ProgramRequirement.Operator.MIN_NUMBER_OF.value
            assert section["data"]["elective_flag"] is True
            assert section["data"]["operator_value"] == 1
            elective_found = True
    
    assert custom_found, "Custom section should still exist"
    assert elective_found, "Elective Courses section should be added"


def test_program_admin_form_preserves_existing_sections():
    """
    ProgramAdminForm should not modify existing default sections
    """
    program = ProgramFactory()
    root = program.get_requirements_root()
    
    # Create both default sections
    required_section = root.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
        elective_flag=False,
    )
    
    elective_section = root.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        title="Elective Courses",
        operator_value=3,  # Custom value
        elective_flag=True,
    )
    
    form = ProgramAdminForm(instance=program)
    requirements = form.initial["requirements"]
    
    # Should have exactly 2 sections (no additions)
    assert len(requirements) == 2
    
    # Find the elective section and verify custom value is preserved
    elective_found = False
    for section in requirements:
        if (section["data"]["title"] == "Elective Courses" and 
            section["data"]["operator"] == ProgramRequirement.Operator.MIN_NUMBER_OF.value and
            section["data"]["elective_flag"]):
            assert section["data"]["operator_value"] == 3  # Custom value preserved
            elective_found = True
            break
    
    assert elective_found, "Existing elective section should be preserved with custom values"