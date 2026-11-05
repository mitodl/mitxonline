# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
