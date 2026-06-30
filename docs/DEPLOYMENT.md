# DataPilot 部署说明

## 目标

推荐把作品集演示部署为 Render Web Service：GitHub 保存源码，Render 根据 `Dockerfile` 构建容器并提供公网 HTTPS 地址。

公开演示使用以下安全边界：

- `DATAPILOT_MODE=demo`：无需 OpenAI API Key，不产生模型调用费用。
- `DATAPILOT_ALLOW_UPLOADS=false`：关闭陌生文件上传，只使用内置样例数据。
- `/health`：供 Render 检查服务是否可用。
- 容器以非 root 用户运行。

## 一、发布 GitHub 仓库

只提交 `datapilot` 目录中的项目文件，不要提交 `.venv`、`.env`、API Key 或本地缓存。

```powershell
git init -b main
git add .
git commit -m "publish DataPilot portfolio project"
git remote add origin https://github.com/<你的用户名>/datapilot-agent.git
git push -u origin main
```

## 二、创建 Render 服务

1. 登录 <https://dashboard.render.com/>。
2. 选择 **New → Blueprint**。
3. 授权 Render 读取刚创建的 GitHub 仓库。
4. 选择仓库后，Render 会读取根目录的 `render.yaml`。
5. 确认服务名和 Free 实例，点击部署。
6. 等待 `/health` 检查通过，记录 Render 分配的 `https://<service>.onrender.com` 地址。

免费实例适合简历演示，不适合生产业务；空闲后的首次访问可能需要等待服务启动。

## 三、启用真实 OpenAI Agent（可选）

在 Render 的 Environment 页面设置：

```text
DATAPILOT_MODE=openai
DATAPILOT_MODEL=gpt-5.4-mini
OPENAI_API_KEY=<在 Render Secret 中填写>
```

API Key 只能放在平台的 Secret/Environment 设置里，不能写入 `.env.example` 的值、截图、README 或 Git 提交。

## 四、部署后验收

依次检查：

1. `/health` 返回 `status=ok`。
2. 首页能够显示 `sales_demo.xlsx`。
3. 点击“开始分析”后状态变为“已完成”。
4. 页面显示关键发现、图表、结果表和只读 SQL。
5. 公开部署的上传区显示“公开环境已关闭文件上传”。
6. GitHub Actions 中的测试与 Ruff 检查通过。
