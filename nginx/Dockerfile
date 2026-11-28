# NOTE: this dockerfile is primarilty for local development only
#       it's primary purpose is to emulate heroku-buildpack-nginx's
#       functionality that compiles config/nginx.conf.erb
# See https://github.com/heroku/heroku-buildpack-nginx/blob/fefac6c569f28182b3459cb8e34b8ccafc403fde/bin/start-nginx
FROM nginx:1.30@sha256:755983e0e0e568e4c86297cc91485d7a6f9fb73e42d8a19cdba3eac9e8b8cfc9

# Logs are configured to a relatic path under /etc/nginx
# but the container expects /var/log
RUN mkdir -p /etc/nginx/logs && ln -sf /var/log/nginx /etc/nginx/logs/

# erb unfortunately needs a whole ruby install
RUN apt-get update && apt-get install -y ruby

COPY --chmod=777 20-compile-nginx-conf-erb.sh /docker-entrypoint.d

# NOTE: this removes the args "-g daemon off" because nginx is impolite
#       and treats a cli flag and a config flag as duplicate:
#
#       nginx: [emerg] "daemon" directive is duplicate in /etc/nginx/nginx.conf:3
#
CMD ["nginx"]
