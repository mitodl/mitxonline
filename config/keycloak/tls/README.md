# TLS Config

If you want to add a different cert, you can here. The files have to be named:

* `tls.crt` - the full chain certficate
* `tls.key` - the key for the certificate

The default certs have `.default` appended to them. These are for the `kc.odl.local` domain. If you're using a different domain (and you care about changing this), you can regenerate the cert using this one-liner:

```bash
openssl req -x509 -newkey rsa:4096 -keyout tls.key -out tls.crt -sha256 -days 3650 -nodes -subj "/C=XX/ST=StateName/L=CityName/O=CompanyName/OU=CompanySectionName/CN=new-hostname"
```

Run from the `config/keycloak/tls` directory (this one) locally. The Keycloak image doesn't have openssl installed so you can't use that.
