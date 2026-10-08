FROM node:20-alpine

WORKDIR /app

# Install dependencies into the image layer.
# node_modules live here; the compose volume mount preserves them
# even when the host source tree is bind-mounted over /app.
COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

# host is set in vite.config.ts (server.host: '0.0.0.0')
CMD ["npm", "run", "dev"]
