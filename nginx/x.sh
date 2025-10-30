#!/bin/sh

# Set default values if not provided
export PORT=${PORT:-3000}
export ACTIVE_POOL=${ACTIVE_POOL:-blue}

envsubst '${ACTIVE_POOL} ${PORT}' < /etc/nginx/templates/nginx.conf.template > /etc/nginx/conf.d/default.conf

# Start nginx in foreground
exec nginx -g "daemon off;"
