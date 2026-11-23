# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2026.11.23.1] - 2026-11-23

### Changes

- **Test that mpd-parser parses a DASH manifest through xmldom** (#4309) by 1447295+shaidar@users.noreply.github.com
- **Update dependency drf-spectacular to >=0.30,<0.31** (#4134) by 29139614+renovate[bot]@users.noreply.github.com
- **Add geolocation and location flagging API** (#4244) by jkachel@mit.edu
- **Split the Stripe checkout return into success and cancel endpoints** (#4297) by jkachel@mit.edu
- **Update nginx:1.30 Docker digest to 7fad6c0** (#4292) by 29139614+renovate[bot]@users.noreply.github.com
- **Call the shared uv.lock revision action** (#4313) by rhysyngsun@users.noreply.github.com
- **Update dependency opentelemetry-api to v1.45.2 [SECURITY]** (#4287) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency dnspython to v2.9.2 [SECURITY]** (#4291) by 29139614+renovate[bot]@users.noreply.github.com
- **Bump mitol-django-apigateway to 2026.11.10** (#4302) by tmacey@mit.edu
- **fix: downgrade every selected enrollment in the admin downgrade action** (#4308) by 88967643+Anas12091101@users.noreply.github.com
- **Add users to Keycloak organizations as a membership-only service account** (#4225) by tmacey@mit.edu
- **Fix the order-history N+1 allowlisted in #4126** (#4187) by christopher.chudzicki@gmail.com
- **Install local-dev's dev deps before the source copy** (#4307) by christopher.chudzicki@gmail.com
- **Docs on verifiable credentials backfill options** (#4306) by dsubak@users.noreply.github.com
- **chore(deps): mitol-django-scim 2026.4.29 -> 2026.11.13** (#4290) by tmacey@mit.edu
- **chore: move to Yarn 4.18.1 with a 7-day npm age gate** (#4310) by 1447295+shaidar@users.noreply.github.com
- **Redirect the MITx Online home page to MIT Learn and remove it** (#4300) by christopher.chudzicki@gmail.com
- **Fix program refund enrollment downgrades** (#4284) by collinp@mit.edu
- **fix: link enrollment, receipt and refund emails to MIT Learn** (#4281) by 88967643+Anas12091101@users.noreply.github.com
- **Drop the courses_courserun.b2b_contract_id column** (#4304) by christopher.chudzicki@gmail.com

## [2026.11.18.2] - 2026-11-18

### Changes

- **Keep contracts when the Keycloak membership call fails** (#4298) by tmacey@mit.edu
- **Update @xmldom/xmldom, minimatch, brace-expansion and fast-uri for security fixes** (#4273) by 1447295+shaidar@users.noreply.github.com
- **Read the edX migration tables from StarRocks or Trino, chosen by a setting** (#4270) by tmacey@mit.edu
- **feat: show the site banner when ecom-service is set** (#4299) by christopher.chudzicki@gmail.com
- **Move Sentry from send_default_pii to data_collection** (#4239) by jkachel@mit.edu
- **Add tests for the OIDC provider, telemetry setup and email CSS inlining** (#4271) by 1447295+shaidar@users.noreply.github.com
- **fix: brand the financial aid form pages as MIT Learn** (#4265) by 88967643+Anas12091101@users.noreply.github.com
- **feat: always send /dashboard/ to MIT Learn and remove the legacy dashboard** (#4278) by 88967643+Anas12091101@users.noreply.github.com
- **Assert uv.lock stays on revision 5** (#4288) by rhysyngsun@users.noreply.github.com
- **Take run order from the database in reconcile_upgrade_deadlines tests** (#4295) by christopher.chudzicki@gmail.com

## [2026.11.16.1] - 2026-11-16

### Changes

- **feat: show the site banner on the cart page** (#4285) by christopher.chudzicki@gmail.com
- **Automatically process eligible refund requests** (#4224) by collinp@mit.edu
- **Update ol-django common and add ol-django geoip** (#4283) by jkachel@mit.edu
- **Drop the uv required-version upper bound** (#4286) by rhysyngsun@users.noreply.github.com
- **fix: let a hand-off from Learn discard a stale gateway session** (#4276) by tmacey@mit.edu
- **Update dependency astral-sh/uv to v0.13.7** (#4293) by 29139614+renovate[bot]@users.noreply.github.com
- **Send Sentry a keyed hash of the user instead of their identity** (#4272) by tmacey@mit.edu
- **Serve a login link with kc_idp_hint for each B2B identity provider** (#4119) by tmacey@mit.edu
- **Keep a path in KEYCLOAK_BASE_URL when building Keycloak URLs** (#4104) by tmacey@mit.edu
- **Add has_live_product_page to the v3 enrollment APIs** (#4280) by gumaerc@mit.edu
- **Skip a program's courses with no valid contract run key, and give a contract with no variant sets no runs** (#4105) by tmacey@mit.edu
- **Run the checkout pre-flight checks through Pluggy hooks** (#4139) by jkachel@mit.edu
- **Move the last Wagtail-edited contract fields into the contract API and staff dashboard** (#4267) by tmacey@mit.edu
- **Default b2b_codes assign --name to blank** (#4268) by tmacey@mit.edu
- **feat: add backfill functionality for edX.org letter grades in migrate_edx_data** (#4274) by rlougee@mit.edu
- **Build the frontend from its own inputs so backend edits reuse the cached bundles** (#4277) by christopher.chudzicki@gmail.com
- **Skip a program's courses with no usable source run, and create its runs for the contract's variant sets** (#4095) by tmacey@mit.edu
- **Bound uv required-version so Renovate stops silently changing the lockfile format** (#4275) by rhysyngsun@users.noreply.github.com
- **fix: point financial aid emails at MIT Learn instead of MITx Online** (#4264) by 88967643+Anas12091101@users.noreply.github.com
- **Update dependency sqlparse to v0.6.0 [SECURITY]** (#4260) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency soupsieve to v2.9 [SECURITY]** (#4259) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency pymongo to v4.18.3 [SECURITY]** (#4258) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency pygments to v2.20.0 [SECURITY]** (#4257) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency pillow-heif to v1.3.0 [SECURITY]** (#4256) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency opentelemetry-api to v1.45.1 [SECURITY]** (#4255) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency lxml to v6.1.0 [SECURITY]** (#4254) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency idna to v3.15 [SECURITY]** (#4253) by 29139614+renovate[bot]@users.noreply.github.com
- **Fix redirect to referer if enrollment fails** (#4242) by jkachel@mit.edu
- **feat(courses): add --dry-run support to migrate_edx_data's users type** (#3842) by 1447295+shaidar@users.noreply.github.com
- **Add tests for the Google Sheets auth and video.js setup paths** (#4269) by 1447295+shaidar@users.noreply.github.com
- **Update dependency httplib2 to v0.32.0 [SECURITY]** (#4252) by 29139614+renovate[bot]@users.noreply.github.com
- **Add tests that exercise real image processing** (#4240) by 1447295+shaidar@users.noreply.github.com
- **Remove the new-issues workflow** (#4235) by 1447295+shaidar@users.noreply.github.com
- **Update dependency pyasn1 to v0.6.5 [SECURITY]** (#4247) by 29139614+renovate[bot]@users.noreply.github.com

## [2026.11.10.1] - 2026-11-10

### Changes

- **Update dependency dnspython to v2.9.0 [SECURITY]** (#4251) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency black to v26.10.1 [SECURITY]** (#4250) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency python-dotenv to v1.2.2 [SECURITY]** (#4249) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency pytest to v9.0.3 [SECURITY]** (#4248) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency jwcrypto to v1.5.7 [SECURITY]** (#4246) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency oauthlib to v4 [SECURITY]** (#4262) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency pyjwt to v2.15.1** (#4218) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency astral-sh/uv to v0.13.6** (#4245) by 29139614+renovate[bot]@users.noreply.github.com
- **Fix certificate revision for certificates** (#3920) by annagav@users.noreply.github.com
- **chore(frontend): remove more unused dependencies** (#4241) by christopher.chudzicki@gmail.com
- **Set username to the lowercased email where it is something else** (#4206) by tmacey@mit.edu
- **Update dependency authlib to v1.9.1 [SECURITY]** (#4197) by 29139614+renovate[bot]@users.noreply.github.com
- **Test pull requests as their merge ref** (#4228) by christopher.chudzicki@gmail.com
- **chore(frontend): split dev dependencies and drop unused packages** (#4237) by 1447295+shaidar@users.noreply.github.com
- **Return test-mode course pages to MIT Learn from /api/v2/pages/** (#4230) by ahiguera@mit.edu
- **Add an identity provider edit form to the staff dashboard** (#4111) by tmacey@mit.edu
- **Fix some basket N+1 's, reduce zeal suppressions** (#4168) by christopher.chudzicki@gmail.com

## [2026.11.5.1] - 2026-11-05

### Changes

- **fix: point $0 program course order refunds at the paid program order** (#4234) by 88967643+Anas12091101@users.noreply.github.com
- **chore(deps): upgrade Pillow to 13.0.0** (#4236) by 1447295+shaidar@users.noreply.github.com
- **Refactor exception handling** (#2988) by 1447295+shaidar@users.noreply.github.com
- **Remove unused YouTube data-src iframe script from base template** (#4231) by 1447295+shaidar@users.noreply.github.com
- **Checkout product with program product ID uses cart flow** (#4207) by annagav@users.noreply.github.com
- **Fix the test_create_edx_user flake and log edX lookup failures** (#4029) by tmacey@mit.edu
- **ci: limit the CI workflow's GITHUB_TOKEN to read-only** (#4232) by 1447295+shaidar@users.noreply.github.com
- **Do not return a parent program's certificate type for courses (e.g., courses do not have Micromaster Credentials)** (#4213) by christopher.chudzicki@gmail.com

## [2026.11.4.1] - 2026-11-04

### Changes

- **Remove legacy b2b_contract FK** (#4066) by jkachel@mit.edu
- **Create contract runs for courses in nested programs** (#4215) by gumaerc@mit.edu
- **Update dockerignore to fix some local build issues** (#4222) by jkachel@mit.edu
- **Refund sheet: validate user email and order** (#4220) by annagav@users.noreply.github.com
- **Stop redux-query retries leaking into later JS tests [DRAFT]** (#4223) by christopher.chudzicki@gmail.com
- **Fix the page-walk N+1s allowlisted in #4126** (#4172) by christopher.chudzicki@gmail.com

## [2026.11.3.1] - 2026-11-03

### Changes

- **Use description field if not blank and flag is enabled.** (#4214) by dsubak@users.noreply.github.com
- **Update dependency astral-sh/uv to v0.13.3** (#4219) by 29139614+renovate[bot]@users.noreply.github.com
- **Add courseware export/import command** (#4212) by jkachel@mit.edu
- **Build media URLs on a configurable domain instead of the S3 bucket** (#4202) by 1447295+shaidar@users.noreply.github.com
- **Undo verification with Program Entitlement** (#4196) by annagav@users.noreply.github.com
- **Remove unused _ensure_target_line_item_for_line** (#4209) by collinp@mit.edu
- **Cull PendingOrders older than 60 days** (#4190) by jkachel@mit.edu
- **Add "Generate with AI" buttons for certificate VC fields** (#4199) by ahiguera@mit.edu
- **Update dependency pyjwt to v2.15.0 [SECURITY]** (#4152) by 29139614+renovate[bot]@users.noreply.github.com
- **docs: point RELEASE.rst at CHANGELOG.md** (#4210) by feoh@feoh.org
- **Update dependency datamodel-code-generator to v0.81.0 [SECURITY]** (#4127) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency faker to >=40.43.0,<=40.43.0** (#4135) by 29139614+renovate[bot]@users.noreply.github.com
- **Update dependency prek to v0.5.5** (#4188) by 29139614+renovate[bot]@users.noreply.github.com
- **Centralize country checks for course enrollment** (#4177) by collinp@mit.edu
- **Add read-only user debug screen to the Django Admin** (#4185) by jkachel@mit.edu
- **Move all payment records when transferring records between accounts** (#4194) by annagav@users.noreply.github.com
- **Remove compliancecheck from admin archived course enrollment** (#4203) by annagav@users.noreply.github.com
- **Add a seed_local_instance command for local development** (#4205) by tmacey@mit.edu

## [2026.10.28.1] - 2026-10-28

### Changes

- **Suppress error with reminders if a user clicks an older email** (#4195) by dsubak@users.noreply.github.com
- **Return the profile fields to fix when CyberSource rejects compliance data** (#4138) by 88967643+Anas12091101@users.noreply.github.com
- **Publish "upgrade" as a valid program enrollment mode** (#4191) by jkachel@mit.edu

## [2026.10.27.1] - 2026-10-27

### Changes

- `a11c87a` Merge branch 'release' by mitx-devops@mit.edu
- **Remove temporary certifi exclude-newer exemption** (#4192) by 34372316+arslanashraf7@users.noreply.github.com
