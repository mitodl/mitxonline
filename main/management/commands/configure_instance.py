"""
Meta-command to help set up a freshly configured MITxOnline instance.

Running this will perform the following functions:
- Configures a superuser account.
- Creates the OAuth2 application record for edX (optionally with an existing
  client ID and secret).
- Creating a program.
- Creating financial assistance tiers, and a flexible price request form for
  the program.
- Creating course entries for the default courses that come with devstack.
- Creating product entries and course about pages for these courses.
- Creating a new learner account, and optionally enrolling them in the course.

The default program is "program-v1:MITx+DEDP" (Data, Economics and Development
Policy), and the two courses that it will make are:
- Demonstration Course (course-v1:edX+DemoX+Demo_Course)
- E2E Test Course (course-v1:edX+E2E-101+course)

The Demonstration Course will be added to the DEDP program but E2E Test Course
will not.

The learner account will have these parameters:
- Username: testlearner
- Email Address: testlearner@mitxonline.odl.local
- Password: you will be prompted for this
- Name: Test Learner
- Country Code: US
- Enrollments: course-v1:edX+DemoX+Demo_Course

The product for the courses will both be $999 so they are under the limit
for test CyberSource transactions.

If the --tutor/-T option is passed, the command will use the local.edly.io
address for links to edX rather than edx.odl.local:18000.

This uses other management commands to complete these tasks. So, if you just
want to run part of this, use one of these commands:
- createsuperuser to create the super user
- configure_wagtail for initial setup of Wagtail assets
- configure_tiers for creating the program tiers and discounts
- create_course for creating the courses and runs
- create_user for creating the learner account (which also uses
  create_enrollment internally)
- sync_courserun for syncing course run data with devstack

There are some steps that this command won't do for you:
- Creating any additional courses/programs/etc.
- Completing the integration between MITxOnline and devstack - there are still
  steps that you need to take to finish that process

"""

from django.core.management import BaseCommand, call_command
from oauth2_provider.models import Application


class Command(BaseCommand):
    """
    Bootstraps a fresh MITxOnline instance.
    """

    def add_arguments(self, parser):
        """Parses command line arguments."""

        parser.add_argument(
            "platform",
            help="Your platform (none, macos, or linux; defaults to none). None skips OAuth2 record creation.",
            type=str,
            choices=["none", "macos", "linux"],
            nargs="?",
            const="none",
        )

        parser.add_argument(
            "--dont-enroll",
            "-D",
            help="Don't enroll the learner in course-v1:edX+DemoX+Demo_Course.",
            action="store_true",
            dest="dont_enroll",
        )

        parser.add_argument(
            "--dont-create-superuser",
            "-S",
            help="Don't create a superuser account.",
            action="store_false",
            dest="superuser",
        )

        parser.add_argument(
            "--edx-oauth-client",
            help="Use the provided OAuth2 client ID, rather than making a new one.",
            type=str,
            nargs="?",
        )

        parser.add_argument(
            "--edx-oauth-secret",
            help="Use the provided OAuth2 client secret, rather than making a new one.",
            type=str,
            nargs="?",
        )

        parser.add_argument(
            "--gateway",
            help="Specify the gateway IP. (Required for Linux users.)",
            type=str,
            nargs="?",
        )

        parser.add_argument(
            "--tutor",
            "-T",
            help="Configure for Tutor.",
            action="store_true",
            dest="tutor",
        )

        parser.add_argument(
            "--tutor-dev",
            help="Configure for Tutor Dev/Nightly.",
            action="store_true",
            dest="tutordev",
        )

    def determine_edx_hostport(self, *args, **kwargs):
        """Returns a tuple of the edX host and port depending on what the user's passed in"""

        if kwargs["tutor"]:
            return ("local.edly.io", "")
        elif kwargs["tutordev"]:
            return ("local.edly.io", ":8000")
        else:
            return ("edx.odl.local:18000", ":18000")

    def handle(self, *args, **kwargs):
        """Coordinates the other commands."""

        (edx_host, edx_gateway_port) = self.determine_edx_hostport(**kwargs)

        # Step -1: run createsuperuesr
        if kwargs["superuser"]:
            self.stdout.write(self.style.SUCCESS("Creating superuser..."))

            call_command("createsuperuser")

        # Step 0: create OAuth2 provider records
        if kwargs["platform"] != "none":
            self.stdout.write(self.style.SUCCESS("Creating OAuth2 app..."))

            if kwargs["platform"] == "macos":
                redirects = "\n".join(
                    [
                        f"http://{edx_host}/auth/complete/mitxpro-oauth2/",
                        f"http://host.docker.internal{edx_gateway_port}/auth/complete/mitxpro-oauth2/",
                    ]
                )
            else:
                if kwargs["gateway"] is None:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Gateway required for platform type {kwargs['platform']}."
                        )
                    )
                    exit(-1)

                redirects = "\n".join(
                    [
                        f"http://{edx_host}/auth/complete/mitxpro-oauth2/",
                        f"http://{kwargs['gateway']}{edx_gateway_port}/auth/complete/mitxpro-oauth2/",
                    ]
                )

            (oauth2_app, created) = Application.objects.get_or_create(
                name="edx-oauth-app",
                defaults={
                    "client_type": "confidential",
                    "authorization_grant_type": "authorization-code",
                    "skip_authorization": True,
                },
            )

            if kwargs["edx_oauth_client"] is not None:
                oauth2_app.client_id = kwargs["edx_oauth_client"]

            if kwargs["edx_oauth_secret"] is not None:
                oauth2_app.client_secret = kwargs["edx_oauth_secret"]

            oauth2_app.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created OAuth2 app {oauth2_app.name} for edX. Your client ID is \n{oauth2_app.client_id}\nand your secret is\n{oauth2_app.client_secret}\n\n"
                )
            )

        # Step 1: run configure_wagtail
        self.stdout.write(self.style.SUCCESS("Configuring Wagtail..."))

        call_command("configure_wagtail")

        # Step 2: create the program
        self.stdout.write(self.style.SUCCESS("Creating the DEDP program..."))

        call_command(
            "create_courseware",
            "program",
            "program-v1:MITx+DEDP",
            "Data, Economics and Development Policy",
            live=True,
            depts="Economics",
            create_depts=True,
        )

        # Step 3: create the program page
        self.stdout.write(self.style.SUCCESS("Creating the DEDP program about page..."))

        call_command("create_courseware_page", "program-v1:MITx+DEDP")

        # Step 4: create the financial aid form
        self.stdout.write(
            self.style.SUCCESS("Creating the DEDP financial asistance form...")
        )

        call_command("create_finaid_form", "program-v1:MITx+DEDP")

        # Step 5: create the courses (incld. course runs and syncing)
        self.stdout.write(
            self.style.SUCCESS("Creating courses and runs to match devstack...")
        )

        call_command(
            "create_courseware",
            "course",
            "course-v1:edX+DemoX",
            "Demonstration Course",
            live=True,
            create_run="Demo_Course",
            run_url=f"http://{edx_host}/courses/course-v1:edX+DemoX+Demo_Course/",
            program="program-v1:MITx+DEDP",
            depts="Science",
            create_depts=True,
        )

        call_command(
            "create_courseware",
            "course",
            "course-v1:edX+E2E-101",
            "E2E Test Course",
            live=True,
            create_run="course",
            run_url=f"http://{edx_host}/courses/course-v1:edX+E2E-101+course/",
            depts="Math",
            create_depts=True,
        )

        self.stdout.write(self.style.SUCCESS("Syncing course runs (this may fail)..."))

        call_command("sync_courserun", all="ALL")

        # Step 6: create course about pages
        self.stdout.write(
            self.style.SUCCESS("Creating the devstack course about pages...")
        )

        call_command("create_courseware_page", "course-v1:edX+DemoX", live=True)
        call_command("create_courseware_page", "course-v1:edX+E2E-101", live=True)

        # Step 7: create the products
        self.stdout.write(
            self.style.SUCCESS("Creating the devstack course products...")
        )

        call_command("create_product", "course-v1:edX+E2E-101+course", 999)
        call_command("create_product", "course-v1:edX+DemoX+Demo_Course", 999)
        call_command(
            "createinitialrevisions", "ecommerce.Product", comment="Initial revision."
        )

        # Step 8: create the learner and enroll them (unless told not to)
        self.stdout.write(self.style.SUCCESS("Creating the learner..."))

        if "dont_enroll" in kwargs and kwargs["dont_enroll"]:
            call_command(
                "create_user",
                "testlearner",
                "testlearner@mitxonline.odl.local",
                "Test",
                "Learner",
                "Test Learner",
                "US",
            )
        else:
            call_command(
                "create_user",
                "testlearner",
                "testlearner@mitxonline.odl.local",
                "Test",
                "Learner",
                "Test Learner",
                "US",
                enroll="course-v1:edX+DemoX+Demo_Course",
            )

        self.stdout.write(self.style.SUCCESS("Done!"))

        if kwargs["platform"] != "none":
            self.stdout.write(
                self.style.SUCCESS(
                    f"== edX OAuth2 Application Details ==\nClient ID: {oauth2_app.client_id}\nSecret: {oauth2_app.client_secret}\n\n"
                )
            )
