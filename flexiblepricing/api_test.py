"""Flexible price api tests"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import ddt
import freezegun
import pytest
import pytz
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.utils.text import slugify
from factory import fuzzy
from mitol.common.utils.datetime import now_in_utc

from cms.factories import ProgramPageFactory
from cms.models import FlexiblePricingRequestForm
from courses.factories import (
    CourseFactory,
    CourseRunFactory,
    ProgramFactory,
    ProgramRunFactory,
)
from courses.models import (
    Course,
    Program,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from ecommerce.factories import ProductFactory
from flexiblepricing.api import (
    IncomeThreshold,
    create_default_flexible_pricing_page,
    determine_auto_approval,
    determine_courseware_flexible_price_discount,
    determine_income_usd,
    determine_tier_courseware,
    import_country_income_thresholds,
    is_courseware_flexible_price_approved,
    parse_country_income_thresholds,
    update_currency_exchange_rate,
)
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.exceptions import CountryIncomeThresholdException
from flexiblepricing.factories import FlexiblePriceFactory, FlexiblePriceTierFactory
from flexiblepricing.models import (
    CountryIncomeThreshold,
    CurrencyExchangeRate,
    FlexiblePrice,
    FlexiblePriceTier,
)
from main.settings import TIME_ZONE
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


def test_parse_country_income_thresholds_no_header(tmp_path):
    """parse_country_income_thresholds should throw error if no header is found"""
    path = tmp_path / "test.csv"
    with (
        Path.open(path, "w"),
        pytest.raises(CountryIncomeThresholdException) as exc,
    ):  # create a file
        parse_country_income_thresholds(path)

    assert exc.value.args[0] == "Unable to find the header row"


def test_parse_country_income_thresholds_missing_header_fields(tmp_path):
    """parse_country_income_thresholds should throw error if any of the header field is missing"""
    path = tmp_path / "test.csv"
    with open(path, "w") as file:  # noqa: PTH123
        file.write("country\n")
        file.write("PK\n")

    with pytest.raises(CountryIncomeThresholdException) as exc:
        parse_country_income_thresholds(path)

    assert exc.value.args[0] == "Unable to find column header income"


def test_parse_country_income_thresholds(tmp_path):
    """parse_country_income_thresholds should convert CSV records into IncomeThreshold objects"""
    path = tmp_path / "test.csv"
    with open(path, "w") as file:  # noqa: PTH123
        file.write("country,income\n")
        file.write("PK,25000\n")
        file.write("US,75000\n")

    income_thresholds = parse_country_income_thresholds(path)
    assert income_thresholds == [
        IncomeThreshold(country="PK", income="25000"),
        IncomeThreshold(country="US", income="75000"),
    ]


@pytest.mark.django_db
def test_import_country_income_thresholds(tmp_path, caplog):
    """Test import_country_income_thresholds works fine"""
    path = tmp_path / "test.csv"
    with open(path, "w") as file:  # noqa: PTH123
        file.write("country,income\n")
        file.write("PK,25000\n")
        file.write("US,75000\n")

    # first time would create new records
    import_country_income_thresholds(path)
    assert "Record created successfully for country=PK with income 25000"  # noqa: PLW0129
    assert "Record created successfully for country=US with income 75000"  # noqa: PLW0129

    # second time would rather update records
    import_country_income_thresholds(path)
    assert "Updated record successfully for country=PK with income 25000"  # noqa: PLW0129
    assert "Updated record successfully for country=US with income 75000"  # noqa: PLW0129


class ExchangeRateAPITests(TestCase):
    """
    Tests for flexible pricing exchange rate api backend
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        CurrencyExchangeRate.objects.create(currency_code="ABC", exchange_rate=1.5)
        CurrencyExchangeRate.objects.create(currency_code="DEF", exchange_rate=1.5)

    def test_update_currency_exchange_rate(self):
        """
        Tests updated_currency_exchange_rate()
        """
        latest_rates = {"ABC": 12.3, "GHI": 7.89}
        descriptions = {"ABC": "Test Code 1", "GHI": "Test Code 2"}
        update_currency_exchange_rate(latest_rates, descriptions)
        assert (
            CurrencyExchangeRate.objects.get(currency_code="ABC").exchange_rate
            == latest_rates["ABC"]
        )
        with self.assertRaises(CurrencyExchangeRate.DoesNotExist):  # noqa: PT027
            CurrencyExchangeRate.objects.get(currency_code="DEF")
        assert (
            CurrencyExchangeRate.objects.get(currency_code="GHI").exchange_rate
            == latest_rates["GHI"]
        )
        assert (
            CurrencyExchangeRate.objects.get(currency_code="ABC").description
            == descriptions["ABC"]
        )
        assert (
            CurrencyExchangeRate.objects.get(currency_code="GHI").description
            == descriptions["GHI"]
        )


def create_courseware(create_tiers=True, past=False):  # noqa: FBT002
    """
    Helper function to create a flexible pricing courseware. Defaults to
    creating a CourseRun.
    Arguments:
        create_tiers: boolean, also create some tiers for the courseware object
        past: boolean, cause the courseware object to end in the past
        create_program: boolean, cause the courseware object to be a Program
    Returns:
        courses.models.Program: A new program
    """
    end_date = None
    program = ProgramFactory.create(live=True)
    root_node = program.requirements_root

    root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )

    course = CourseFactory.create()
    program.add_requirement(course)

    if past:
        end_date = now_in_utc() - timedelta(days=100)
    else:
        end_date = now_in_utc() + timedelta(days=100)

    ProgramRunFactory.create(end_date=end_date, program=program)
    CourseRunFactory.create(
        end_date=end_date,
        enrollment_end=now_in_utc() + timedelta(hours=1),
        course=course,
    )

    course_tiers = program_tiers = None
    if create_tiers:
        course_tiers = {
            "0k": FlexiblePriceTierFactory.create(
                courseware_object=course, income_threshold_usd=0, current=True
            ),
            "25k": FlexiblePriceTierFactory.create(
                courseware_object=course, income_threshold_usd=25000, current=True
            ),
            "50k": FlexiblePriceTierFactory.create(
                courseware_object=course, income_threshold_usd=50000, current=True
            ),
            "75k": FlexiblePriceTierFactory.create(
                courseware_object=course,
                income_threshold_usd=75000,
                current=True,
                discount__amount=0,
            ),
        }
        program_tiers = {
            "0k": FlexiblePriceTierFactory.create(
                courseware_object=program, income_threshold_usd=0, current=True
            ),
            "25k": FlexiblePriceTierFactory.create(
                courseware_object=program, income_threshold_usd=25000, current=True
            ),
            "50k": FlexiblePriceTierFactory.create(
                courseware_object=program, income_threshold_usd=50000, current=True
            ),
            "75k": FlexiblePriceTierFactory.create(
                courseware_object=program,
                income_threshold_usd=75000,
                current=True,
                discount__amount=0,
            ),
        }

    return course, course_tiers, program, program_tiers


class FlexiblePriceBaseTestCase(TestCase):
    """
    Base test case for financial aid test setup
    """

    @classmethod
    def setUpTestData(cls):
        # replace imported thresholds with fake ones created here
        CountryIncomeThreshold.objects.all().delete()

        (
            cls.course,
            cls.course_tiers,
            cls.program,
            cls.program_tiers,
        ) = create_courseware()
        cls.country_income_threshold_0 = CountryIncomeThreshold.objects.create(
            country_code="0",
            income_threshold=0,
        )
        CountryIncomeThreshold.objects.create(
            country_code="50",
            income_threshold=50000,
        )

        # Create a FinancialAid with a reset status to verify that it is ignored
        FlexiblePriceFactory.create(
            # user="US",  # noqa: ERA001
            tier=cls.course_tiers["75k"],
            status=FlexiblePriceStatus.RESET,
        )
        FlexiblePriceFactory.create(
            # user="US",  # noqa: ERA001
            tier=cls.program_tiers["75k"],
            status=FlexiblePriceStatus.RESET,
        )

    @staticmethod
    def make_http_request(
        method, url, status, data=None, content_type="application/json", **kwargs
    ):
        """
        Helper method for asserting an HTTP status. Returns the response for further tests if needed.
        Args:
            method (method): which http method to use (e.g. self.client.put)
            url (str): url for request
            status (int): http status code
            data (dict): data for request
            content_type (str): content_type for request
            **kwargs: any additional kwargs to pass into method
        Returns:
            rest_framework.response.Response
        """
        if data is not None:
            kwargs["data"] = json.dumps(data)
        resp = method(url, content_type=content_type, **kwargs)
        assert resp.status_code == status
        return resp


@ddt.ddt
class FlexiblePriceAPITests(FlexiblePriceBaseTestCase):
    """
    Tests for financialaid api backend
    """

    def setUp(self, test_program=True):  # noqa: FBT002
        self.test_program = test_program

        super().setUp()

        if test_program:
            self.courseware_object = self.program
            self.tiers = self.program_tiers
        else:
            self.courseware_object = self.course
            self.tiers = self.course_tiers

        self.program.refresh_from_db()
        self.course.refresh_from_db()

    def select_course_or_program(self, test_program=False):  # noqa: FBT002
        """
        Helper to swap between a course or program for testing.
        """
        self.courseware_object = self.program if test_program else self.course
        self.tiers = self.program_tiers if test_program else self.course_tiers

    @ddt.data(
        [0, "0k"],
        [1000, "0k"],
        [25000, "25k"],
        [27500, "25k"],
        [50000, "50k"],
        [72800, "50k"],
        [75000, "75k"],
        [34938234, "75k"],
    )
    @ddt.unpack
    def test_determine_tier_courseware(self, income, expected_tier_key):
        """
        Tests determine_tier_courseware() assigning the correct tiers. This should assign the tier where the tier's
        income threshold is equal to or less than income.
        """
        assert (
            determine_tier_courseware(self.program, income)
            == self.program_tiers[expected_tier_key]
        )
        assert (
            determine_tier_courseware(self.course, income)
            == self.program_tiers[expected_tier_key]
        )
        self.program.requirements_root.get_descendants().filter(
            course=self.course
        ).delete()

        reload_course = Course.objects.get(pk=self.course.id)

        assert (
            determine_tier_courseware(reload_course, income)
            == self.course_tiers[expected_tier_key]
        )

    @ddt.data(True, False)  # noqa: FBT003
    def test_determine_tier_courseware_not_current(self, test_program=False):  # noqa: FBT002
        """
        A current=False tier should be ignored
        """
        courseware_object = self.program if test_program else self.course
        not_current = FlexiblePriceTierFactory.create(
            courseware_object=courseware_object,
            income_threshold_usd=75000,
            current=False,
        )
        assert determine_tier_courseware(courseware_object, 34938234) != not_current

    def test_determine_tier_courseware_improper_setup(self):
        """
        Tests that determine_tier_courseware() raises ImproperlyConfigured if no $0-discount TierProgram
        has been created and income supplied is too low.
        """
        program = ProgramFactory.create()

        course = CourseFactory.create()
        program.add_requirement(course)

        with self.assertRaises(ImproperlyConfigured):  # noqa: PT027
            determine_tier_courseware(course, 0)

    @ddt.data(
        [0, "0", True],
        [1, "0", True],
        [0, "50", False],
        [49999, "50", False],
        [50000, "50", False],
        [50001, "50", True],
        [0, "0", True, True],
        [1, "0", True, True],
        [0, "50", False, True],
        [49999, "50", False, True],
        [50000, "50", False, True],
        [50001, "50", True, True],
    )
    @ddt.unpack
    def test_determine_auto_approval(
        self,
        income_usd,
        country_code,
        expected,
        test_program=False,  # noqa: FBT002
    ):
        """
        Tests determine_auto_approval() assigning the correct auto-approval status. This should return True
        if income is strictly greater than the threshold (or if the threshold is 0, which is inclusive of 0).
        """
        self.select_course_or_program(test_program)

        flexible_price = FlexiblePriceFactory.create(
            income_usd=income_usd,
            country_of_income=country_code,
        )
        courseware_tier = determine_tier_courseware(self.courseware_object, income_usd)
        assert determine_auto_approval(flexible_price, courseware_tier) is expected

    def create_run_and_product_and_discount(self, user, courseware_object):
        """
        Helper function to pull out creating the course/program run and the
        product for the tests that follow.
        """
        if type(courseware_object) is Program:
            run_obj = ProgramRunFactory.create(program=courseware_object)
        else:
            run_obj = CourseRunFactory.create(course=courseware_object)

        product = ProductFactory.create(purchasable_object=run_obj)

        return determine_courseware_flexible_price_discount(product, user)

    def create_fp_and_compare_tiers(
        self, courseware_object, income_usd, country_code, user, expected
    ):
        """
        Helper function to pull out the actual FP record creation and
        orchestration to DRY up some tests. This does not do the assertions
        since that changes from test to test.
        """

        content_type = (
            ContentType.objects.get(app_label="courses", model="program")
            if isinstance(courseware_object, Program)
            else ContentType.objects.get(app_label="courses", model="course")
        )

        if not FlexiblePrice.objects.filter(
            user=user,
            courseware_content_type=content_type,
            courseware_object_id=courseware_object.id,
        ).exists():
            flexible_price = FlexiblePriceFactory.create(  # noqa: F841
                income_usd=income_usd,
                country_of_income=country_code,
                user=user,
                courseware_object=courseware_object,
                status=FlexiblePriceStatus.APPROVED
                if expected
                else FlexiblePriceStatus.PENDING_MANUAL_APPROVAL,
            )

        courseware_tier = determine_tier_courseware(courseware_object, income_usd)
        discount = self.create_run_and_product_and_discount(user, courseware_object)

        return courseware_tier, discount

    @ddt.data(
        [0, "0", True],
        [1, "0", True],
        [0, "50", False],
        [49999, "50", False],
        [50000, "50", False],
        [50001, "50", True],
        [0, "0", True, True],
        [1, "0", True, True],
        [0, "50", False, True],
        [49999, "50", False, True],
        [50000, "50", False, True],
        [50001, "50", True, True],
    )
    @ddt.unpack
    def test_determine_courseware_flexible_price_discount(
        self,
        income_usd,
        country_code,
        expected,
        test_program=False,  # noqa: FBT002
    ):
        """
        Tests for the correct application of the flexible price discount.
        """
        self.select_course_or_program(test_program)

        user = UserFactory.create()
        courseware_tier, discount = self.create_fp_and_compare_tiers(
            self.courseware_object, income_usd, country_code, user, expected
        )

        if expected:
            assert discount.amount == courseware_tier.discount.amount
        else:
            assert discount is None

    def test_determine_courseware_flexible_price_discount_anonymous_user(self):
        """
        Tests discount is `None` for anonymous user.
        """
        self.select_course_or_program(test_program=False)

        user = AnonymousUser()
        run_obj = CourseRunFactory.create(course=self.courseware_object)
        product = ProductFactory.create(purchasable_object=run_obj)
        discount = determine_courseware_flexible_price_discount(product, user)
        assert discount is None

    def test_determine_courseware_flexible_price_discount_expired(self):
        """
        Tests the result of determine_courseware_flexible_price_discount when
        the discount has expired.
        """
        self.select_course_or_program()

        user = UserFactory.create()
        course = CourseFactory.create()
        product = ProductFactory.create(purchasable_object=course)
        flexible_price = FlexiblePriceFactory.create(
            income_usd=12000,
            user=user,
            courseware_object=course,
            status=FlexiblePriceStatus.APPROVED,
        )
        discount = flexible_price.tier.discount

        assert discount.activation_date is None and discount.expiration_date is None  # noqa: PT018
        assert determine_courseware_flexible_price_discount(product, user) == discount

        expired_delta = timedelta(days=30)
        discount.activation_date = (
            datetime.now(pytz.timezone(TIME_ZONE)) - expired_delta - expired_delta
        )
        discount.expiration_date = (
            datetime.now(pytz.timezone(TIME_ZONE)) - expired_delta
        )
        with freezegun.freeze_time(
            datetime.now(pytz.timezone(TIME_ZONE)) - expired_delta * 3
        ):
            discount.save()
            discount.refresh_from_db()

        assert (  # noqa: PT018
            discount.activation_date is not None
            and discount.expiration_date is not None
        )
        assert (
            determine_courseware_flexible_price_discount(product, user) is not discount
        )

    @ddt.data(
        [0, "0", True],
        [1, "0", True],
        [0, "50", False],
        [49999, "50", False],
        [50000, "50", False],
        [50001, "50", True],
    )
    @ddt.unpack
    def test_determine_courseware_flexible_pricing_hierarchy(
        self, income_usd, country_code, expected
    ):
        """
        Tests the application hierarchy for flexible pricing requests.
        Courses with a program attached should grab the tier for the program if
        they belong to a program.
        Courses with a program attached and that have their own tier should use
        the program tier unless the program has no tiers.
        Courses that are standalone should grab a tier that they're attached to
        directly.

        Program application is covered in the preceding test.
        """
        user = UserFactory.create()

        # Step 1: course that belongs to a program - should get back the program tiers
        course, course_tiers, program, program_tiers = create_courseware()
        course.program = program
        course.save()
        course.refresh_from_db()
        courseware_tier, discount = self.create_fp_and_compare_tiers(
            course, income_usd, country_code, user, expected
        )

        if expected:
            assert discount.amount == courseware_tier.discount.amount
            assert courseware_tier.courseware_object == program
        else:
            assert discount is None

        # Step 2: we'll remove the program tiers - should now get back the course tiers
        FlexiblePriceTier.objects.filter(courseware_object_id=program.id).delete()
        course.refresh_from_db()
        courseware_tier, discount = self.create_fp_and_compare_tiers(
            course, income_usd, country_code, user, expected
        )

        if expected:
            assert discount.amount == courseware_tier.discount.amount
            assert courseware_tier.courseware_object == course
        else:
            assert discount is None

        # Step 3: standalone course
        course.program = None
        course.save()
        program.delete()
        course.refresh_from_db()
        course.refresh_from_db()
        courseware_tier, discount = self.create_fp_and_compare_tiers(
            course, income_usd, country_code, user, expected
        )

        if expected:
            assert discount.amount == courseware_tier.discount.amount
            assert courseware_tier.courseware_object == course
        else:
            assert discount is None

    def test_determine_income_usd_from_not_usd(self):
        """
        Tests determine_income_usd() from a non-USD currency
        """
        CurrencyExchangeRate.objects.create(currency_code="GHI", exchange_rate=1.5)
        assert determine_income_usd(3000, "GHI") == 2000

    def test_determine_income_usd_from_usd(self):
        """
        Tests determine_income_usd() from a USD currency
        """
        # Note no CurrencyExchangeRate created here
        assert determine_income_usd(5000, "USD") == 5000

    @ddt.data(
        [True],
        [False],
    )
    @ddt.unpack
    def test_is_courseware_flexible_price_approved(
        self,
        is_approved,
    ):
        status = (
            FlexiblePriceStatus.APPROVED
            if is_approved
            else FlexiblePriceStatus.PENDING_MANUAL_APPROVAL
        )
        flexible_price_record = FlexiblePriceFactory(status=status)
        result = is_courseware_flexible_price_approved(
            user=flexible_price_record.user,
            course_run=flexible_price_record.courseware_object,
        )
        assert is_approved == result


@pytest.mark.parametrize(
    "courseware_type,force_course,gen_slug,gen_title",  # noqa: PT006
    [
        ("course", False, False, False),
        ("program", False, False, False),
        ("courseprogram", False, False, False),
        ("course", False, True, True),
        ("program", False, True, True),
        ("courseprogram", False, True, True),
        ("courseprogram", True, False, False),
        ("coursemultipleprogram", False, False, False),
        ("coursemultipleprogram", True, False, False),
    ],
)
def test_create_finaid_form(courseware_type, force_course, gen_slug, gen_title):
    """
    Tests the automated financial assistance form code.
    """

    if courseware_type == "course":
        courseware = CourseFactory.create()
        page = courseware.page
    elif courseware_type == "program":
        page = ProgramPageFactory.create()
        courseware = page.program
    else:
        program_page = ProgramPageFactory.create()
        courseware = CourseFactory.create()
        program_page.program.add_requirement(courseware)

        if courseware_type == "coursemultipleprogram":
            second_program = ProgramPageFactory.create()
            second_program.program.add_requirement(courseware)

        if force_course:  # noqa: SIM108
            page = courseware.page
        else:
            page = program_page

    test_kwargs = {
        "slug": str(fuzzy.FuzzyText()) if gen_slug else None,
        "title": str(fuzzy.FuzzyText()) if gen_title else None,
    }

    generated_page = create_default_flexible_pricing_page(
        courseware, force_course, **test_kwargs
    )

    assert isinstance(generated_page, FlexiblePricingRequestForm)
    assert generated_page.live is False

    if test_kwargs["slug"] is not None:
        assert generated_page.slug == slugify(test_kwargs["slug"])
    if test_kwargs["title"] is not None:
        assert generated_page.title == test_kwargs["title"]

    assert generated_page.get_parent() == page

    if (
        courseware_type == "course"
        or (courseware_type == "courseprogram" and force_course)
        or (courseware_type == "coursemultipleprogram" and force_course)
    ):
        assert generated_page.selected_course == courseware
    elif (
        courseware_type == "courseprogram" or courseware_type == "coursemultipleprogram"  # noqa: PLR1714
    ) and not force_course:
        assert generated_page.selected_program == courseware.programs[0]
    else:
        assert generated_page.selected_program == courseware
