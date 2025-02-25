# MITx Online Keycloak Integration

The Compose file includes a Keycloak instance that you can use for authentication instead of spinning up a separate one or using one of the deployed instances. It's not enabled by default, but you can run it if you prefer not to run your own Keycloak instance.

_If you're running the pack-in Keycloak with other apps (Unified Ecommerce, Learn), you might just want to use its instance instead._ There's instructions below on doing that. Start at "Configuring MITx Online" below.

## Default Settings

These are the defaults configured for the system.

### Ports and Hostname

By default, the Keycloak instance listens on ports `7080` and `7443` and the hostname it expects is `kc.odl.local`. If you want to change this, set these in your `.env` file:

- `KEYCLOAK_SVC_HOSTNAME`
- `KEYCLOAK_PORT`
- `KEYCLOAK_SSL_PORT`

### SSL Certificate

 There's a self-signed cert that's in `config/keycloak/tls` - if you'd rather set up your own (or you have a real cert or something to use), you can drop the PEM files in there. See the README there for info.

### Realm and App Users

There's a `default-realm.json` in `config/keycloak` that will get loaded by Keycloak when it starts up, and will set up a realm for you with some users and a client so you don't have to set it up yourself. The realm it creates is called `ol-local`.

The _`ol_local`_ users it sets up are:

| User | Password |
|---|---|
| `student@odl.local` | `student` |
| `prof@odl.local` | `prof` |
| `admin@odl.local` | `admin` |

> These will not get you into the Keycloak admin interface.

The default realm contains an OIDC client called `apisix`. You can get or change the secrets from within the Keycloak Admin, or you can create a new client if you wish.

These users are in groups, but the groups don't mean anything by default.

### Keycloak Admin

The Keycloak admin interface is at `https://kc.odl.local:7443` by default. As noted, the `ol-local` users above won't get you access to this interface. A separate admin account is configured on first run for this. By default, the credentials are `admin`/`admin` but you can change this by setting these in your `.env`:
- `KEYCLOAK_SVC_ADMIN`
- `KEYCLOAK_SVC_ADMIN_PASSWORD`

_You probably shouldn't change these, though._ If you want to use a different admin user/password, log into the Keycloak admin after first bringing the container up and create a new user in the Master realm. (There will also be a banner at the top instructing you to do so.)

## Making it Work

The Keycloak instance is hidden in the `keycloak` profile in the Composer file, so if you want to interact with it, you'll need to run `docker compose --profile keycloak`, or add `COMPOSE_PROFILES=keycloak` to your `.env` file. (If you start the app without the profile, you can still start Keycloak later by specifying the profile.)

### Database Config

If you're **starting from scratch** (no volumes, containers, etc.), the database container should pick up the init script in `config/db` and create a user and database for Keycloak. No further configuration is needed.

If you're starting with **an existing database**: you will need to create a Keycloak user and database. The easiest way to do it is to just run the `config/db/init-keycloak.sql` script against your running database.

### First Start

1. In `config/keycloak/tls`, copy `tls.crt.default` and `tls.key.default` to `tls.crt` and `tls.key`. (Or, you can regenerate them - see the README in that folder.)
2. Set Keycloak environment values in your `.env` file. Most of these are described above, and none are required.
   - `KEYCLOAK_SVC_KEYSTORE_PASSWORD` - password for the keystore Keycloak will create
   - `KEYCLOAK_SVC_ADMIN`
   - `KEYCLOAK_SVC_ADMIN_PASSWORD`
   - `KEYCLOAK_SVC_HOSTNAME`
   - `KEYCLOAK_PORT`
   - `KEYCLOAK_SSL_PORT`
3. Start the Keycloak service: `docker compose --profile keycloak up -d keycloak`

The Keycloak container should start and stay running. Once it does, you should be able to log in at `https://kc.odl.local:7443/` with username and password `admin` (or the values you supplied).

## Configuring MITx Online

To use the Keycloak instance with MITx Online, you need to set these in your `.env` file:

- `SOCIAL_AUTH_OL_OIDC_OIDC_ENDPOINT` - root endpoint for OIDC for the realm (see below)
- `SOCIAL_AUTH_OL_OIDC_KEY` - client ID - if you're using the defaults, this is `apisix`
- `SOCIAL_AUTH_OL_OIDC_SECRET` - client secret

These settings can be found in the Keycloak admin. It's easiest to bring Keycloak up on its own via `docker compose up keycloak` to get these values, then bring the rest of the system up later.

The endpoint URL is available in the Keycloak admin. Open the realm you wish to use - `ol-local` for the pack in one - then navigate to `Realm settings` under Configure. At the bottom of the `General` tab, the URL you want is the `OpenID Endpoint Configuration` link. This will be a URL like `http://kc.odl.local:7080/realms/ol-local/.well-known/openid-configuration` You will need to remove the `.well-known/openid-configuration` from this.

> The endpoint URL should be the **HTTP** version of this, unless you have a real certificate on your Keycloak instance. Otherwise, you'll get certificate errors.

> The endpoint URL isn't listed here because you have to go get the secret anyway. Additionally, the endpoint URL can change when new Keycloak versions are released, so it's better to get it out of the admin interface.

The key and secret are available under `Clients`. The key is the client name (so, by default, `apisix`) and the secret is available under `Credentials` once you open the client configuration.

### Other Keycloak Instances

You can use MITx Online with Keycloak instances that aren't the pack-in one - the provided one is just for convenience. Just set the same settings above, but get them from whatever Keycloak instance you already have running.

_If you're running Keycloak alongside MITx Online on the same machine,_ you will need to perform some additional configuration to make it visible to MITx Online. Docker containers and Compose projects can't generally see each other, and local-only hostnames (e.g. hosts file entries) don't apply inside containers. You can get around this by setting up a composer override file that adds an alias for the hostname you're using for the Keycloak instance to `host-gateway`. There's a sample override file called `docker-compose-keycloak-override.yml` you can use for this.

### SSO Admins

If you're using MITx Online with Keycloak, you can technically skip creating a superuser. Instead, you can log in with the account you want to use as a superuser account (e.g. `admin@odl.local`) and then use the `promote_user` command to add privileges:

`promote_user --promote --superuser admin@odl.local`

This can also be used to demote users or promote only to staff; see its help for more info. The account must exist first so the user must have logged in before you can run the command.

## Troubleshooting

A few things to check if you run into issues:

- _Redirect loop_: Your sessions have gotten into a weird state. Clear cookies for anything at `odl.local` (or whatever domain you're using).
- _Slowness when loading_: (macOS especially) Make sure your `/etc/hosts` contains equivalent entries for `::1` (IPv6 loopback) for your local hostnames. (macOS will generally prefer IPv6 over IPv4.)
- _Errors about discovery_: Make sure the discovery URL (`SOCIAL_AUTH_OL_OIDC_OIDC_ENDPOINT`) is correct. If Keycloak has updated, it may not be. Additionally, make sure you're connecting to the right ports - if you've changed them, the discovery URL may be somewhere else now.
