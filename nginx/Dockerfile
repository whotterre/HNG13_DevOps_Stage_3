FROM nginx:latest

RUN set -eux \
	&& apt-get update \
	&& DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gettext-base \
	&& rm -rf /var/lib/apt/lists/*

RUN mkdir -p /etc/nginx/templates

COPY nginx.conf.template /etc/nginx/templates/nginx.conf.template

COPY x.sh /x.sh

RUN chmod +x /x.sh

CMD ["/x.sh"]