FROM mcr.microsoft.com/playwright:v1.53.0-noble

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

COPY assets/ ./assets/
COPY config/ ./config/
COPY server.js ./

RUN mkdir -p /data

EXPOSE 8790

CMD ["node", "server.js"]
