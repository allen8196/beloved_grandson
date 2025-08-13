# RespiraAlly ｜ COPD 個案管理儀表板—結構化 Prompt（給 Cursor 直接生程式｜含 API 串接）

> 目標：以 **React** 快速建立三分頁儀表板（**病患整體趨勢總覽、病患個案管理、使用狀態**），**串接目前已存在的 API**，並預留「群體彙總/即時通報」等**缺項端點**的待辦。此文件可直接貼入 Cursor 作為生成提示，產出可開發的前端原型。

---

## 一、設計原則（Style 與 UX）

- **對象**：呼吸治療師（中高齡友善、臨床決策支援）。
- **字體與大小**：`Noto Sans TC`；基準 `18px`；KPI/標題 `20–24px`；可點擊元素最小 `44×44px`。
- **色彩（參考圖醫療清爽風）**
  `--bg-top:#E9F2FF`（頂部標題底色） / `--primary:#7CC6FF` / `--purple:#CBA6FF` / `--mint:#B8F2E6` / `--danger:#E66A6A` / 文字 `#2C3E50`、輔助 `#6B7280`。
- **可用性**：高對比、明確層級、KPI 卡可掃視；圖表必有 Tooltip、Legend、空值狀態。
- **布局**：左側固定 `<nav>`、中間主內容、右側輔助欄；行動版右欄折疊為抽屜。

**全域樣式（直接建立 `src/index.css` 或全域 Style 區塊）：**

```css
:root {
  --bg-top: #e9f2ff;
  --primary: #7cc6ff;
  --purple: #cba6ff;
  --mint: #b8f2e6;
  --danger: #e66a6a;
  --text: #2c3e50;
  --muted: #6b7280;
  --card: #ffffff;
  --shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}
body {
  font-family: "Noto Sans TC", system-ui, -apple-system, Segoe UI, Roboto,
    "PingFang TC", "Microsoft JhengHei", sans-serif;
  color: var(--text);
  background: linear-gradient(180deg, #f7faff 0%, #fdfeff 100%);
}
.header {
  background: var(--bg-top);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}
.card {
  background: var(--card);
  border-radius: 16px;
  box-shadow: var(--shadow);
  padding: 16px;
}
.kpi {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(160px, 1fr));
}
.chart {
  min-height: 280px;
}
.nav {
  width: 240px;
  background: linear-gradient(180deg, #ecf6ff, #f7f5ff);
  padding: 16px;
}
.rightPane {
  width: 280px;
}
.btn {
  padding: 10px 14px;
  border-radius: 12px;
  background: var(--primary);
  color: white;
  font-weight: 600;
}
.badge {
  padding: 4px 10px;
  border-radius: 99px;
  background: #eef6ff;
  color: #2563eb;
}
```

---

## 二、API 串接清單（以現有為主）

> 來源：`API文件.csv`（共 20 條）。以下按功能分組，**直接對應前端頁面**。

### A. 個案層（已存在，可直接串接）

- 病患列表（治療師底下）：`GET /api/v1/therapist/patients`
- 個案健康檔案：`GET /api/v1/patients/{patient_id}/profile`
- 個案每日健康日誌（CRUD）：

  - 讀：`GET /api/v1/patients/{patient_id}/daily_metrics`
  - 新增：`POST /api/v1/patients/{patient_id}/daily_metrics`
  - 更新：`PUT  /api/v1/patients/{patient_id}/daily_metrics/{log_id}`

- CAT：`GET|POST|PUT /api/v1/patients/{patient_id}/questionnaires/cat`
- mMRC：`GET|POST|PUT /api/v1/patients/{patient_id}/questionnaires/mmrc`
- 對話紀錄（選配）：

  - 個案對話清單：`GET /api/v1/patients/{patient_id}/conversations`
  - 單會話訊息：`GET /api/v1/conversations/{conversation_id}/messages`

### B. 認證與上傳

- 登入：`POST /api/v1/auth/login`、LINE 登入：`POST /api/v1/auth/line/login|register`
- 取得音檔上傳 URL：`POST /audio/request-url`

### C. 缺項（需新增之彙總/通報端點）

- **總覽（群體 KPI/趨勢/依從性）**：

  - `GET /api/overview/kpis?date_from&date_to`
  - `GET /api/overview/trends?metric=cat,mmrc&bucket=month`
  - `GET /api/overview/adherence?bucket=week`

- **個案 KPI 彙總**：

  - `GET /api/patient/{id}/kpis?date_from&date_to`

- **使用狀態**：

  - `GET /api/usage/reporting-calendar?date_from&date_to`
  - `GET /api/usage/distribution?by=risk|therapist&date_from&date_to`

- **AI 即時通報**：

  - `GET /api/alerts/live`（SSE/WebSocket；短期可輪詢 `/api/alerts?since=`）

> 臨時策略：缺項未完成前，前端以 **mock** 或後端臨時彙總視圖（debug 端點）代位，功能旗標切換。

---

## 三、路由與頁面需求（含指標與對應 API）

### 1) /overview ｜病患整體趨勢總覽

- **全局篩選**：`date_from`, `date_to`, `risk`
- **KPI 卡**（需新增 `overview/kpis`）：患者總數、高風險比、低依從性比、CAT 平均、mMRC 平均
- **圖表**：

  1. CAT & mMRC 每月平均趨勢（`overview/trends`）
  2. 高風險與低依從性佔比（`overview/kpis` 或 `overview/distribution`）
  3. 四大健康追蹤依從性趨勢（`overview/adherence`）

### 2) /cases ｜病患個案管理（列表 + 詳情 /cases/\:id）

- **列表**：`GET /api/v1/therapist/patients`（支援 `q`, `risk`, `limit`, `offset`）
- **詳情**（\:id）：

  - 基本資料：`GET /api/v1/patients/{id}/profile`
  - KPI（建議新增）：`GET /api/patient/{id}/kpis?date_from&date_to`，短期由前端從下列端點就地運算：

    - CAT 最新：`GET CAT` 歷史中取最近
    - mMRC 最新：`GET mMRC` 歷史中取最近
    - 7d 用藥遵從、回報率、完成率、距最近回報天數：由 `GET daily_metrics` 滾動彙整

  - 趨勢圖：

    - 健康追蹤：`GET daily_metrics`（`water_cc, medication, exercise_min, cigarettes`）
    - 量表趨勢：`GET CAT`、`GET mMRC`

  - 右側「智慧建議」：依 KPI 規則在前端渲染（後續可搬到 BE）

### 3) /usage ｜使用狀態

- **KPI**：7d 回報率、7d 用藥遵從、7d 完成率、平均距最近回報天數（建議由 `usage/*` 提供）
- **圖表**：

  1. 回報熱力曆（`usage/reporting-calendar`）
  2. 使用分布（依風險/治療師，`usage/distribution`）

### 右側輔助欄（全域）

- 病患搜尋（本地於列表之上）
- 高風險病患列表：由 `GET /api/v1/therapist/patients` 取得後端標籤/或前端依 CAT/mMRC 規則排序
- AI 即時通報：`GET /api/alerts/live`（缺項，先以輪詢代位）

---

## 四、React 專案腳手架與 Hooks（整合現有 API）

**技術棧**：Vite + React + React Router + React Query + Recharts + Day.js

**路由**：`/overview`、`/cases`（列表）、`/cases/:id`（詳情）、`/usage`

**元件樹**

```
App
 ├─ SidebarNav
 ├─ Header（頂部底色 var(--bg-top)，含日期/風險篩選）
 ├─ Routes
 │   ├─ OverviewPage
 │   │   ├─ KpiRow
 │   │   ├─ TrendCatMmrcChart
 │   │   ├─ RiskAdherencePie
 │   │   └─ BehaviorAdherenceTrend
 │   ├─ CasesPage
 │   │   ├─ PatientListPane（右側：搜尋 + 高風險清單）
 │   │   └─ PatientDetail（/:id）
 │   │       ├─ PatientProfileCard
 │   │       ├─ PatientKpis
 │   │       ├─ PatientMetricsSmallMultiples
 │   │       └─ EvaluationSuggestions
 │   └─ UsagePage
 │       ├─ ReportingCalendarHeatmap
 │       └─ UsageDistributionChart
 └─ RightPane（全域 AI 即時通報）
```

**API Hooks（以現有端點可用、缺項預留）**

```ts
// src/api/hooks.ts
import { useQuery } from "@tanstack/react-query";

export const usePatients = (params: any) =>
  useQuery({
    queryKey: ["patients", params],
    queryFn: () =>
      fetch(`/api/v1/therapist/patients?${new URLSearchParams(params)}`).then(
        (r) => r.json()
      ),
  });

export const usePatientProfile = (id: string) =>
  useQuery({
    enabled: !!id,
    queryKey: ["patient-profile", id],
    queryFn: () =>
      fetch(`/api/v1/patients/${id}/profile`).then((r) => r.json()),
  });

export const usePatientMetrics = (id: string, params: any) =>
  useQuery({
    enabled: !!id,
    queryKey: ["patient-metrics", id, params],
    queryFn: () =>
      fetch(
        `/api/v1/patients/${id}/daily_metrics?${new URLSearchParams(params)}`
      ).then((r) => r.json()),
  });

export const useCatHistory = (id: string, params: any) =>
  useQuery({
    enabled: !!id,
    queryKey: ["cat-history", id, params],
    queryFn: () =>
      fetch(
        `/api/v1/patients/${id}/questionnaires/cat?${new URLSearchParams(
          params
        )}`
      ).then((r) => r.json()),
  });

export const useMmrcHistory = (id: string, params: any) =>
  useQuery({
    enabled: !!id,
    queryKey: ["mmrc-history", id, params],
    queryFn: () =>
      fetch(
        `/api/v1/patients/${id}/questionnaires/mmrc?${new URLSearchParams(
          params
        )}`
      ).then((r) => r.json()),
  });

// 缺項：群體彙總 & 個案 KPI & 即時通報（先禁用，待後端完成改為 enabled:true）
export const useOverviewKpis = (params: any) =>
  useQuery({
    enabled: false,
    queryKey: ["ov-kpis", params],
    queryFn: () =>
      fetch(`/api/overview/kpis?${new URLSearchParams(params)}`).then((r) =>
        r.json()
      ),
  });
export const useOverviewTrends = (params: any) =>
  useQuery({
    enabled: false,
    queryKey: ["ov-trends", params],
    queryFn: () =>
      fetch(`/api/overview/trends?${new URLSearchParams(params)}`).then((r) =>
        r.json()
      ),
  });
export const useOverviewAdherence = (params: any) =>
  useQuery({
    enabled: false,
    queryKey: ["ov-adh", params],
    queryFn: () =>
      fetch(`/api/overview/adherence?${new URLSearchParams(params)}`).then(
        (r) => r.json()
      ),
  });
export const usePatientKpis = (id: string, params: any) =>
  useQuery({
    enabled: false,
    queryKey: ["p-kpis", id, params],
    queryFn: () =>
      fetch(`/api/patient/${id}/kpis?${new URLSearchParams(params)}`).then(
        (r) => r.json()
      ),
  });
export const useAlertsLive = () => {
  /* SSE/WebSocket：待 BE */
};
```

---

## 五、元件到 API 的對映表

| 元件                         | 使用端點                                  | 備註                             |
| ---------------------------- | ----------------------------------------- | -------------------------------- |
| PatientListPane              | `GET /api/v1/therapist/patients`          | 支援 `q` `risk` `limit` `offset` |
| PatientProfileCard           | `GET /api/v1/patients/{id}/profile`       | health_profiles 合併顯示         |
| PatientMetricsSmallMultiples | `GET /api/v1/patients/{id}/daily_metrics` | 小倍數圖：水/藥/運/菸            |
| TrendCatMmrcChart（個案）    | `GET CAT`、`GET mMRC`                     | 取歷史；前端畫折線               |
| PatientKpis                  | `GET /api/patient/{id}/kpis`（缺）        | 未就緒前由前端就地計算           |
| TrendCatMmrcChart（總覽）    | `GET /api/overview/trends`（缺）          | 月桶聚合                         |
| RiskAdherencePie             | `GET /api/overview/kpis`（缺）            | 風險/依從性比例                  |
| BehaviorAdherenceTrend       | `GET /api/overview/adherence`（缺）       | 週桶趨勢                         |
| ReportingCalendarHeatmap     | `GET /api/usage/reporting-calendar`（缺） | 熱力曆                           |
| UsageDistributionChart       | `GET /api/usage/distribution`（缺）       | 依風險/治療師分布                |
| RightPane Alerts             | `GET /api/alerts/live`（缺）              | SSE / 輪詢替代                   |

---

## 六、缺項端點—回傳格式建議（摘要）

```http
GET /api/overview/kpis?date_from&date_to
200 {"patients_total":123,"high_risk_pct":0.27,"low_adherence_pct":0.31,"cat_avg":13.2,"mmrc_avg":1.4}

GET /api/overview/trends?metric=cat,mmrc&bucket=month
200 [{"date":"2025-04-01","cat_avg":13.5,"mmrc_avg":1.4}]

GET /api/overview/adherence?bucket=week
200 [{"date":"2025-W18","med_rate":0.82,"water_rate":0.74,"exercise_rate":0.69,"smoke_tracking_rate":0.91}]

GET /api/patient/{id}/kpis?date_from&date_to
200 {"cat_latest":16,"mmrc_latest":2,"adherence_7d":0.86,"report_rate_7d":0.71,"completion_7d":0.75,"last_report_days":2}

GET /api/usage/reporting-calendar?date_from&date_to
200 [{"date":"2025-08-01","reports_count":57}]

GET /api/usage/distribution?by=risk&date_from&date_to
200 [{"group":"高風險","report_rate_7d":0.66,"adherence_med_7d":0.61,"completion_7d":0.58,"avg_last_report_days":3.2}]

GET /api/alerts/live  (SSE)
event: alert
data: {"id":"a1","ts":"2025-08-11T06:32:01Z","level":"warning","message":"近7日用藥遵從率下降 >20%"}
```

---

## 七、驗收條件（前端）

- 路由與頁面可切換，頂部標題具有底色（`var(--bg-top)`）。
- 個案頁：列表 → 詳情 → 圖表渲染成功；缺項 API 未完成時以 mock 顯示並提示「待後端」。
- 總覽、使用頁：能以 mock 呈現結構，當 `overview/*`、`usage/*` 端點開啟後無須改動 UI 即可切換。
- 右側欄：可搜尋病患、顯示高風險清單、保留 AI 通報位。

---

### 指示（請 Cursor 依此生成專案）—完整版

> 以 **React + Vite + React Router + React Query + Recharts + TypeScript** 建專案；先串接**已存在的 API**，缺項端點以 **Mock**（MSW 或內建假資料）代位，後續用 Feature Flag 切換。

#### 0. 專案建立與依賴

```bash
# 建立專案
npm create vite@latest respira-ally-dashboard -- --template react-ts
cd respira-ally-dashboard

# 必要套件
npm i @tanstack/react-query react-router-dom recharts dayjs
# 可選：UI/圖示
npm i clsx
# Mock：選 MSW（建議）或先用內建假資料
npm i -D msw

# 型別與開發工具
npm i -D @types/node @types/react @types/react-dom
```

#### 1. 環境變數與常數

- 建立 `.env`：

```
VITE_API_BASE=/api
```

- 建立 `src/config.ts`：

```ts
export const API_BASE = import.meta.env.VITE_API_BASE || "/api";
```

#### 2. 檔案結構（最小骨架）

```
src/
  api/
    hooks.ts
    client.ts
  components/
    KpiRow.tsx
    TrendCatMmrcChart.tsx
    RiskAdherencePie.tsx
    BehaviorAdherenceTrend.tsx
    PatientListPane.tsx
    PatientProfileCard.tsx
    PatientKpis.tsx
    PatientMetricsSmallMultiples.tsx
    EvaluationSuggestions.tsx
    ReportingCalendarHeatmap.tsx
    UsageDistributionChart.tsx
  layout/
    Header.tsx
    SidebarNav.tsx
    RightPane.tsx
  pages/
    OverviewPage.tsx
    CasesPage.tsx
    PatientDetail.tsx
    UsagePage.tsx
  styles/
    index.css  # 直接貼上「全域樣式」CSS 區塊
  main.tsx
  App.tsx
```

#### 3. 全域設定（Query + Router + 樣式）

- 在 `src/main.tsx`：注入 `QueryClientProvider`、`BrowserRouter`，並引入 `styles/index.css`。
- 在 `src/App.tsx`：

  - 版面：左側 `<SidebarNav/>`、頂部 `<Header/>`（頂部底色 `var(--bg-top)`）、右側 `<RightPane/>`、中間 `<Outlet/>`。
  - 路由：`/overview`、`/cases`、`/cases/:id`、`/usage`，預設導向 `/overview`。

#### 4. API Client 與 Hooks

- `src/api/client.ts`

```ts
import { API_BASE } from "../config";
export const api = (path: string, init?: RequestInit) =>
  fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  }).then(async (r) => (r.ok ? r.json() : Promise.reject(await r.text())));
```

- `src/api/hooks.ts`（**現有端點先啟用，缺項先 `enabled:false`**）

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
export const usePatients = (params: any) =>
  useQuery({
    queryKey: ["patients", params],
    queryFn: () => api(`/v1/therapist/patients?${new URLSearchParams(params)}`),
  });
export const usePatientProfile = (id: string) =>
  useQuery({
    enabled: !!id,
    queryKey: ["patient-profile", id],
    queryFn: () => api(`/v1/patients/${id}/profile`),
  });
export const usePatientMetrics = (id: string, p: any) =>
  useQuery({
    enabled: !!id,
    queryKey: ["patient-metrics", id, p],
    queryFn: () =>
      api(`/v1/patients/${id}/daily_metrics?${new URLSearchParams(p)}`),
  });
export const useCatHistory = (id: string, p: any) =>
  useQuery({
    enabled: !!id,
    queryKey: ["cat", id, p],
    queryFn: () =>
      api(`/v1/patients/${id}/questionnaires/cat?${new URLSearchParams(p)}`),
  });
export const useMmrcHistory = (id: string, p: any) =>
  useQuery({
    enabled: !!id,
    queryKey: ["mmrc", id, p],
    queryFn: () =>
      api(`/v1/patients/${id}/questionnaires/mmrc?${new URLSearchParams(p)}`),
  });
// 缺項（待後端）：
export const useOverviewKpis = (p: any) =>
  useQuery({
    enabled: false,
    queryKey: ["ov-kpis", p],
    queryFn: () => api(`/overview/kpis?${new URLSearchParams(p)}`),
  });
export const useOverviewTrends = (p: any) =>
  useQuery({
    enabled: false,
    queryKey: ["ov-trend", p],
    queryFn: () => api(`/overview/trends?${new URLSearchParams(p)}`),
  });
export const useOverviewAdherence = (p: any) =>
  useQuery({
    enabled: false,
    queryKey: ["ov-adh", p],
    queryFn: () => api(`/overview/adherence?${new URLSearchParams(p)}`),
  });
export const usePatientKpis = (id: string, p: any) =>
  useQuery({
    enabled: false,
    queryKey: ["p-kpis", id, p],
    queryFn: () => api(`/patient/${id}/kpis?${new URLSearchParams(p)}`),
  });
```

#### 5. 頁面骨架（以「可運行」為目標）

- `OverviewPage.tsx`

  - 讀取：`useOverviewKpis`、`useOverviewTrends`、`useOverviewAdherence`（初期可用假資料替代）。
  - 元件：`<KpiRow/>`、`<TrendCatMmrcChart/>`、`<RiskAdherencePie/>`、`<BehaviorAdherenceTrend/>`。

- `CasesPage.tsx`

  - 左側列表：`usePatients` + 搜尋/風險篩選。
  - 右側詳情路由 `/cases/:id`：渲染 `<PatientDetail/>`。

- `PatientDetail.tsx`

  - 讀取：`usePatientProfile`、`usePatientMetrics`、`useCatHistory`、`useMmrcHistory`。
  - KPI：先在前端就地計算（7d adherence/report/completion、last_report_days；等 `/patient/{id}/kpis` 完成切換）。
  - 圖表：小倍數（四項）、CAT\&mMRC 趨勢。

- `UsagePage.tsx`

  - 讀取：`useOverviewAdherence` 或 mock。
  - 圖表：`ReportingCalendarHeatmap`、`UsageDistributionChart`。

#### 6. 假資料/Mock（缺項端點暫代）

- 選 **MSW**：

  - 建立 `src/mocks/handlers.ts`，攔截 `/overview/*`、`/patient/:id/kpis`、`/usage/*` 回傳靜態或隨機資料。
  - `src/main.tsx` 中在開發模式下啟用 `worker.start()`。

- 或先在頁面內建 `const demo = [...]`，並以 `enabled:false` 的 hook 改為使用本地資料渲染。

#### 7. UI/樣式落地

- 將本文件「全域樣式」CSS 直接貼到 `styles/index.css`。
- 所有卡片容器加 `.card`、圖表區加 `.chart`，KPI 區使用 `.kpi`。
- Header 使用 `.header` 並置入日期/風險篩選元件（URLSearchParams 同步）。

#### 8. 可用性/可存取性

- 每張圖表需 `aria-label`、`Tooltip`、`Legend`。
- KPI 顯示單位與說明；缺資料時顯示空狀態。

#### 9. 功能旗標（缺項切換）

- 建立 `src/flags.ts`：

```ts
export const FLAGS = {
  OVERVIEW_READY: false,
  USAGE_READY: false,
  PATIENT_KPIS_READY: false,
};
```

- 頁面中以 `FLAGS.*` 決定呼叫 API 或顯示 mock/提示。

#### 10. 驗收清單（最小可用）

- `/cases` 列表可搜尋與篩選；點選進入 `/cases/:id` 能載入個案資料與四項圖表。
- `/overview`、`/usage` 能在 Mock 資料下渲染圖表與 KPI；切旗標即改呼叫後端。
- Header 具有頂部底色（`var(--bg-top)`），與全局日期/風險篩選。
- 右側欄位保留 AI 通報區位（未實作可 placeholder）。

#### 11. 之後要做（後端就緒後）

- 啟用 `useOverview*` 與 `usePatientKpis`，移除 Mock。
- 新增 `useAlertsLive`（SSE/WebSocket）或輪詢替代。
- 若導入 AE 事件：新增 `useAeEvents` 與總覽 AE 指標圖。
