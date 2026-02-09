# 前端 Dockerfile
# 使用 Node.js 18 作為基礎映像
FROM node:18-alpine as build

# 設定工作目錄
WORKDIR /app

# 複製 package 檔案
COPY package*.json ./

# 安裝依賴
RUN npm install

# 複製應用程式碼
COPY . .

# 建置應用程式
RUN npm run build

# 使用 nginx 提供靜態檔案服務
FROM nginx:alpine

# 複製建置結果到 nginx
COPY --from=build /app/build /usr/share/nginx/html

# 複製 nginx 配置（如果需要自訂配置）
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 啟動 nginx
CMD ["nginx", "-g", "daemon off;"]
