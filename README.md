# mitxonline
mitX Online

**SECTIONS**
1. [Initial Setup](#initial-setup)

# Initial Setup

mitxonline follows the same [initial setup steps outlined in the common OL web app guide](http://mitodl.github.io/handbook/common-web-app-guide.html).
Run through those steps **including the addition of `/etc/hosts` aliases and the optional step for running the
`createsuperuser` command**.

### Configure mitxonline and Open edX

See [Configure Open edX](docs/source/configuration/open_edx.rst)

### Configuring the CMS

There are a few changes that must be made to the CMS for the site
to be usable. You can apply all of those changes by running a management command:

```
docker-compose run --rm web ./manage.py configure_wagtail
```

### Configuring Refine Admin

See [Configure Refine Admin](docs/source/configuration/refine_admin.rst)

# Running, testing, and administering the app

Running, testing, and administering this app follows the same patterns as our other web apps. 

*Note: for js tests, run the commands in `frontend/public`, or run via `yarn workspaces foreach run <command>` from the root.

[See the common OL web app guide](http://mitodl.github.io/handbook/common-web-app-guide.html#running-and-accessing-the-app).


# Certificates

In order to manage the certificates, follow these steps:

* Create Signatories (In CMS, go to Pages-> HomePage -> Signatories and then add child pages). Signatories are independent of courses and a signatory can be used with any number of certificates
* Create Certificate Template (In CMS, go to Pages -> Courses -> (Your Course Page) and add a certificate child page). Note that this is course based which means you need to create separate templates for each course
* User certificates are automatically created through a regular task, but you can test these by adding manual entries in CourseRunCertificate model (This is only recommended for local testing because it will make the data inconsistent with payment and grades)
