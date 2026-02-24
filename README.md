# mitxonline
MITx Online

**SECTIONS**
1. [Initial Setup](#initial-setup)

# Initial Setup

mitxonline follows the same [initial setup steps outlined in the common OL web app guide](https://mitodl.github.io/handbook/how-to/common-web-app-guide.html).
Run through those steps **including the addition of `/etc/hosts` aliases and the optional step for running the
`createsuperuser` command**.

### Keycloak Integration

See `README-keycloak.md` for information on setting MITx Online to authenticate via Keycloak. A sample Keycloak instance is included (but not enabled by default), or you can use an external one.

### Configure mitxonline and Open edX

See MITx Online integration with edx:
- [Using Tutor](https://github.com/mitodl/handbook/tree/master/openedx/MITx-edx-integration-tutor.md) (Recommended)
- [Using Devstack](https://github.com/mitodl/handbook/tree/master/openedx/MITx-edx-integration-devstack.md) (Deprecated)

### B2B Provisioning

If you need to get the B2B system set up, see the docs here: [docs/source/configuration/b2b.rst](docs/source/configuration/b2b.rst) (or find them in the build Sphinx docs).

# Running, testing, and administering the app

Running, testing, and administering this app follows the same patterns as our other web apps.

*Note: for js tests, run the commands in `frontend/public`, or run via `yarn workspaces foreach run <command>` from the root.

[See the common OL web app guide](http://mitodl.github.io/handbook/how-to/common-web-app-guide.html#running-and-accessing-the-app).


# Certificates

In order to manage the certificates, follow these steps:

* Create Signatories (In CMS, go to Pages-> HomePage -> Signatories and then add child pages). Signatories are independent of courses and a signatory can be used with any number of certificates
* Create Certificate Template (In CMS, go to Pages -> Courses -> (Your Course Page) and add a certificate child page). Note that this is course based which means you need to create separate templates for each course
* User certificates are automatically created through a regular task, but you can test these by adding manual entries in CourseRunCertificate model (This is only recommended for local testing because it will make the data inconsistent with payment and grades)


# Updating python dependencies

Python dependencies are managed with uv.  If you need to add a new dependency, run this command:

```
docker compose run --rm web uv add <dependency>
```
This will update the `pyproject.toml` and `uv.lock` files.  Then run `docker-compose build web celery` to make the change permanent in your docker images.
Refer to the [uv documentation](https://docs.astral.sh/uv/reference/cli/) for particulars about specifying versions, removing dependencies, etc.


# Generating documentation

Detailed documentation for the project is available in the `docs/` folder. The files within are reStructuredText and can be built into an HTML version using Sphinx. The project uses Pants to manage this build process.

You will need `scie-pants` to build the docs. You can get this by:

- Running the included `get-pants.sh` script
- Installing using the [instructions in the official docs](https://www.pantsbuild.org/stable/docs/getting-started/installing-pants)
- Installing via your package manager (`brew` fo macOS, etc.)

Once you have it installed, you can build the docs:

```bash
pants docs ::
```

The HTML version of the docs starts at `dist/sphinx/index.html`.

If you're adding new docs, remember that this uses reStructuredText - you may find a tool like [m2r](https://github.com/miyakogi/m2r) handy (so you can write in Markdown instead). Don't forget to add links to your new content in the appropriate `index.rst` files.
