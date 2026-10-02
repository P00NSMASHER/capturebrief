FROM node:20-alpine

WORKDIR /app
COPY package.json ./
COPY server.mjs ./
COPY smoke.mjs ./
COPY runtime-smoke.mjs ./
COPY payment-smoke.mjs ./
COPY lib ./lib

ENV NODE_ENV=production
EXPOSE 3000

RUN npm run check && node smoke.mjs && node payment-smoke.mjs

CMD ["node", "server.mjs"]
